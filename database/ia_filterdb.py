from struct import pack
import re
import base64
from typing import Dict, List
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import *
from utils import get_settings, save_group_settings
from collections import defaultdict
from datetime import datetime, timedelta
from logging_helper import LOGGER


_db_stats_cache_primary = {
    "timestamp": None,
    "primary_size": 0
}
_db_stats_cache_secondary = {
    "timestamp": None,
    "primary_size": 0
}

client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

client2 = AsyncIOMotorClient(DATABASE_URI2)
db2 = client2[DATABASE_NAME]
instance2 = Instance.from_db(db2)


@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

@instance2.register
class Media2(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

async def check_db_size(db, cache):
    try:
        now = datetime.utcnow()
        cache_stale = cache["timestamp"] is None or \
                      (now - cache["timestamp"] > timedelta(minutes=10))
        if not cache_stale:
            return cache["primary_size"]
        dbstats = await db.command("dbStats")
        db_size = dbstats['dataSize'] + dbstats['indexSize']
        db_size_mb = db_size / (1024 * 1024) 
        cache["primary_size"] = db_size_mb
        cache["timestamp"] = now
        return db_size_mb
    except Exception as e:
        LOGGER.error(f"Error Checking Database Size: {e}")
        return 0 
    
async def save_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"[_\-\.#+$%^&*()!~`,;:\"'?/<>\[\]{}=|\\]", " ", str(media.file_name))
    file_name = re.sub(r"\s+", " ", file_name).strip()    
    primary_db_size = await check_db_size(db, _db_stats_cache_primary)
    use_secondary = False
    saveMedia = Media
    exists_in_primary = await Media.count_documents({'file_id': file_id}, limit=1)
    if exists_in_primary:
        LOGGER.info(f'{file_name} Is Already Saved In Primary Database!')
        return False, 0
        
    if MULTIPLE_DB and primary_db_size >= DB_CHANGE_LIMIT:
        LOGGER.info("Primary Database Is Low On Space. Switching To Secondary DB.")
        saveMedia = Media2
        use_secondary = True
        exists_in_secondary = await Media2.count_documents({'file_id': file_id}, limit=1)
        if exists_in_secondary:
            LOGGER.info(f'{file_name} Is Already Saved In Secondary Database!')
            return False, 0
            
    try:
        file = saveMedia(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
    except ValidationError as e:
        LOGGER.error(f'Validation Error While Saving File: {e}')
        return False, 2
    else:
        try:
            await file.commit()
        except DuplicateKeyError:
            LOGGER.error(f'{file_name} Is Already Saved In {"Secondary" if use_secondary else "Primary"} Database')
            return False, 0
        else:
            LOGGER.info(f'{file_name} Saved Successfully In {"Secondary" if use_secondary else "Primary"} Database')
            return True, 1
            

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings.get('max_btn') else int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            max_results = 10 if settings.get('max_btn') else int(MAX_B_TN)

    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r"(\b|[\.\+\-_])" + query + r"(\b|[\.\+\-_])"
    else:
        raw_pattern = query.replace(" ", r".*[\s\.\+\-_()\[\]]")

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []
    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}
    if file_type:
        filter['file_type'] = file_type
    total_results = await Media.count_documents(filter)
    if MULTIPLE_DB:
        total_results += await Media2.count_documents(filter)
    if max_results % 2 != 0:
        logger.info(f"Since max_results Is An Odd Number ({max_results}), Bot Will Use {max_results + 1} As max_results To Make It Even.")
        max_results += 1
    cursor1 = Media.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
    files1 = await cursor1.to_list(length=max_results)
    if MULTIPLE_DB:
        remaining_results = max_results - len(files1)
        cursor2 = Media2.find(filter).sort('$natural', -1).skip(offset).limit(remaining_results)
        files2 = await cursor2.to_list(length=remaining_results)
        files = files1 + files2
    else:
        files = files1
    next_offset = offset + len(files)
    if next_offset >= total_results:
        next_offset = ''
    return files, next_offset, total_results
    
async def get_bad_files(query, file_type=None):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r"(\b|[\.\+\-_])" + query + r"(\b|[\.\+\-_])"
    else:
        raw_pattern = query.replace(" ", r".*[\s\.\+\-_()]")
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []
    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}
    if file_type:
        filter['file_type'] = file_type
    cursor1 = Media.find(filter).sort('$natural', -1)
    files1 = await cursor1.to_list(length=(await Media.count_documents(filter)))
    if MULTIPLE_DB:
        cursor2 = Media2.find(filter).sort('$natural', -1)
        files2 = await cursor2.to_list(length=(await Media2.count_documents(filter)))
        files = files1 + files2
    else:
        files = files1
    total_results = len(files)
    return files, total_results
    

async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    if not filedetails:
        cursor2 = Media2.find(filter)
        filedetails = await cursor2.to_list(length=1)
    return filedetails


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref

async def siletxbotz_fetch_media(limit: int) -> List[dict]:
    try:
        if MULTIPLE_DB:
            db_size = await check_db_size(Media)
            if db_size > DB_CHANGE_LIMIT:
                cursor = Media2.find().sort("$natural", -1).limit(limit)
                files = await cursor.to_list(length=limit)
                return files
        cursor = Media.find().sort("$natural", -1).limit(limit)
        files = await cursor.to_list(length=limit)
        return files
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_fetch_media: {e}")
        return []

async def silentxbotz_clean_title(filename: str, is_series: bool = False) -> str:
    try:
        year_match = re.search(r"^(.*?(\d{4}|\(\d{4}\)))", filename, re.IGNORECASE)
        if year_match:
            title = year_match.group(1).replace('(', '').replace(')', '') 
            return re.sub(r"[._\-\[\]@()]+", " ", title).strip().title()
        if is_series:
            season_match = re.search(r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?", filename, re.IGNORECASE)
            if season_match:
                title = season_match.group(1).strip()
                season = season_match.group(2) or season_match.group(3) or season_match.group(4)
                title = re.sub(r"[._\-\[\]@()]+", " ", title).strip().title()
                return f"{title} S{int(season):02}"
        return re.sub(r"[._\-\[\]@()]+", " ", filename).strip().title()
    except Exception as e:
        LOGGER.error(f"Error in truncate_title: {e}")
        return filename
        
async def siletxbotz_get_movies(limit: int = 20) -> List[str]:
    try:
        cursor = await siletxbotz_fetch_media(limit * 2)
        results = set()
        pattern = r"(?:s\d{1,2}|season\s*\d+|season\d+)(?:\s*combined)?(?:e\d{1,2}|episode\s*\d+)?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            caption = getattr(file, "caption", "")
            if not (re.search(pattern, file_name, re.IGNORECASE) or re.search(pattern, caption, re.IGNORECASE)):
                title = await silentxbotz_clean_title(file_name)
                results.add(title)
            if len(results) >= limit:
                break
        return sorted(list(results))[:limit]
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_get_movies: {e}")
        return []

async def siletxbotz_get_series(limit: int = 30) -> Dict[str, List[int]]:
    try:
        cursor = await siletxbotz_fetch_media(limit * 5)
        grouped = defaultdict(list)
        pattern = r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?(?:E(\d{1,2})|Episode\s*(\d+))?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            caption = getattr(file, "caption", "")
            match = None
            if file_name:
                match = re.search(pattern, file_name, re.IGNORECASE)
            if not match and caption:
                match = re.search(pattern, caption, re.IGNORECASE)
            if match:
                title = await silentxbotz_clean_title(match.group(1), is_series=True)
                season = int(match.group(2) or match.group(3) or match.group(4))
                grouped[title].append(season)
        return {title: sorted(set(seasons))[:10] for title, seasons in grouped.items() if seasons}
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_get_series: {e}")
        return []
# Add these methods to your Database class
# Copy and paste these into your database.py file

class Database:
    # ... your existing methods ...
    
    async def update_user_activity(self, user_id):
        """Update user's last activity timestamp"""
        from datetime import datetime
        try:
            await self.col.update_one(
                {"id": user_id},
                {"$set": {"last_active": datetime.utcnow()}},
                upsert=True
            )
        except Exception as e:
            # Don't crash if this fails
            pass
    
    async def get_live_users_count(self):
        """Count users who were active in the last 5 minutes"""
        try:
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(minutes=5)
            return await self.col.count_documents({
                "last_active": {"$gte": cutoff_time}
            })
        except:
            return 0
    
    async def new_users_today(self):
        """Count users who joined today"""
        try:
            from datetime import datetime, timedelta
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            return await self.col.count_documents({
                "date": {"$gte": today_start}
            })
        except:
            return 0
    
    async def new_users_this_week(self):
        """Count users who joined this week"""
        try:
            from datetime import datetime, timedelta
            week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            return await self.col.count_documents({
                "date": {"$gte": week_start}
            })
        except:
            return 0
    
    async def new_users_this_month(self):
        """Count users who joined this month"""
        try:
            from datetime import datetime
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return await self.col.count_documents({
                "date": {"$gte": month_start}
            })
        except:
            return 0
    
    async def new_users_this_year(self):
        """Count users who joined this year"""
        try:
            from datetime import datetime
            year_start = datetime.utcnow().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return await self.col.count_documents({
                "date": {"$gte": year_start}
            })
        except:
            return 0
    
    async def active_users_week(self):
        """Count users who were active in the last 7 days"""
        try:
            from datetime import datetime, timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            return await self.col.count_documents({
                "last_active": {"$gte": week_ago}
            })
        except:
            return 0
    
    async def banned_users_count(self):
        """Count banned users"""
        try:
            return await self.col.count_documents({
                "banned": True
            })
        except:
            return 0
    
    async def blocked_bot_users_count(self):
        """Count users who have blocked the bot"""
        try:
            return await self.col.count_documents({
                "blocked_bot": True
            })
        except:
            return 0
    
    async def mark_user_blocked(self, user_id):
        """Mark a user as having blocked the bot"""
        try:
            from datetime import datetime
            await self.col.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "blocked_bot": True,
                        "blocked_date": datetime.utcnow()
                    }
                }
            )
        except:
            pass
    
    async def mark_user_unblocked(self, user_id):
        """Mark a user as having unblocked the bot"""
        try:
            await self.col.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "blocked_bot": False
                    },
                    "$unset": {
                        "blocked_date": ""
                    }
                }
            )
        except:
            pass


# Optional: Migration script to add missing fields to existing users
async def migrate_user_fields():
    """Add missing fields to existing users"""
    try:
        from datetime import datetime
        
        # Add last_active field
        result1 = await db.col.update_many(
            {"last_active": {"$exists": False}},
            {"$set": {"last_active": datetime.utcnow()}}
        )
        
        # Add banned field
        result2 = await db.col.update_many(
            {"banned": {"$exists": False}},
            {"$set": {"banned": False}}
        )
        
        # Add blocked_bot field
        result3 = await db.col.update_many(
            {"blocked_bot": {"$exists": False}},
            {"$set": {"blocked_bot": False}}
        )
        
        print(f"Migration complete:")
        print(f"- Added last_active to {result1.modified_count} users")
        print(f"- Added banned to {result2.modified_count} users") 
        print(f"- Added blocked_bot to {result3.modified_count} users")
        
    except Exception as e:
        print(f"Migration failed: {e}")


# Run this once to migrate existing users
# asyncio.run(migrate_user_fields())
