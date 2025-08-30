# handlers/spell_check.py

import asyncio
import logging
import re
from fuzzywuzzy import process
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from info import temp
from Script import script
from utils import get_poster, imdb
from database.ia_filterdb import get_search_results
from filters.auto_filter import auto_filter

logger = logging.getLogger(__name__)


async def ai_spell_check(chat_id, wrong_name):
    """AI-powered spell checking using IMDB search"""
    async def search_movie(wrong_name):
        search_results = imdb.search_movie(wrong_name)
        movie_list = [movie['title'] for movie in search_results]
        return movie_list
    
    movie_list = await search_movie(wrong_name)
    if not movie_list:
        return
    
    for _ in range(5):
        closest_match = process.extractOne(wrong_name, movie_list)
        if not closest_match or closest_match[1] <= 80:
            return
            
        movie = closest_match[0]
        files, _, _ = await get_search_results(chat_id=chat_id, query=movie)
        
        if files:
            return movie
            
        movie_list.remove(movie)


async def advantage_spell_chok(client, message):
    """Handle spell checking and movie suggestions"""
    search = message.text
    chat_id = message.chat.id
    
    # Clean the search query
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", message.text, flags=re.IGNORECASE
    )
    query = query.strip() + " movie"
    
    try:
        movies = await get_poster(search, bulk=True)
    except Exception as e:
        logger.exception(f"Error getting poster: {e}")
        k = await message.reply(script.I_CUDNT.format(message.from_user.mention))
        await asyncio.sleep(60)
        await k.delete()
        try:
            await message.delete()
        except:
            pass
        return
    
    if not movies:
        google = search.replace(" ", "+")
        button = [[InlineKeyboardButton(
            "🔍 ᴄʜᴇᴄᴋ sᴘᴇʟʟɪɴɢ ᴏɴ ɢᴏᴏɢʟᴇ 🔍", 
            url=f"https://www.google.com/search?q={google}"
        )]]
        
        k = await message.reply_text(
            text=script.I_CUDNT.format(search), 
            reply_markup=InlineKeyboardMarkup(button)
        )
        await asyncio.sleep(60)
        await k.delete()
        try:
            await message.delete()
        except:
            pass
        return
    
    user = message.from_user.id if message.from_user else 0
    buttons = [
        [InlineKeyboardButton(
            text=movie.get('title'), 
            callback_data=f"spol#{movie.movieID}#{user}"
        )]
        for movie in movies
    ]
    
    buttons.append([InlineKeyboardButton(
        text="🚫 ᴄʟᴏsᴇ 🚫", 
        callback_data='close_data'
    )])
    
    d = await message.reply_text(
        text=script.CUDNT_FND.format(message.from_user.mention), 
        reply_markup=InlineKeyboardMarkup(buttons), 
        reply_to_message_id=message.id
    )
    
    await asyncio.sleep(60)
    await d.delete()
    try:
        await message.delete()
    except:
        pass


@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    """Handle spell check movie selection"""
    _, id, user = query.data.split('#')
    
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(
            script.ALRT_TXT.format(query.from_user.first_name), 
            show_alert=True
        )
    
    movies = await get_poster(id, id=True)
    if not movies:
        return await query.answer("Movie not found", show_alert=True)
        
    movie = movies.get('title')
    movie = re.sub(r"[:-]", " ", movie)
    movie = re.sub(r"\s+", " ", movie).strip()
    
    await query.answer(script.TOP_ALRT_MSG)
    
    files, offset, total_results = await get_search_results(
        query.message.chat.id, movie, offset=0, filter=True
    )
    
    if files:
        k = (movie, files, offset, total_results)
        await auto_filter(bot, query, k)
    else:
        reqstr1 = query.from_user.id if query.from_user else 0
        reqstr = await bot.get_users(reqstr1)
        
        # Log to bin channel if enabled
        if hasattr(__import__('info'), 'NO_RESULTS_MSG') and __import__('info').NO_RESULTS_MSG:
            try:
                await bot.send_message(
                    chat_id=__import__('info').BIN_CHANNEL, 
                    text=script.NORSLTS.format(reqstr.id, reqstr.mention, movie)
                )
            except Exception as e:
                print(f"Error In Spol - {e} Make Sure Bot Admin BIN CHANNEL")
        
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔰Cʟɪᴄᴋ ʜᴇʀᴇ & ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴀᴅᴍɪɴ🔰", 
                url=__import__('info').OWNER_LNK
            )
        ]])
        
        k = await query.message.edit(script.MVE_NT_FND, reply_markup=btn)
        await asyncio.sleep(10)
        await k.delete()
