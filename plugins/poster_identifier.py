import time
import asyncio
import os
import logging
import requests
import base64
import json
from io import BytesIO
from PIL import Image
from typing import Optional, Dict, Any
import google.generativeai as genai
from pyrogram import Client, filters
import platform
import shutil
from pyrogram.types import BotCommand
from info import ADMINS

CMD = ["/", "."]
Bot_cmds = {
    # ... your existing commands ...
    "identify": "Identify K-drama posters from images",
    "poster": "Show poster identification help", 
    "dramas": "List known dramas in database",
    "status": "Show poster identification status (admin only)"
}
# Configure logging
logger = logging.getLogger(__name__)

# Poster Identification Plugin Integration
class PosterIdentifier:
    """K-Drama poster identification functionality."""
    
    def __init__(self):
        """Initialize the poster identifier."""
        self.setup_ai_model()
        self.kdrama_db = self.load_kdrama_database()
    
    def setup_ai_model(self):
        """Setup AI model for image analysis."""
        try:
            gemini_key = os.getenv('AIzaSyCd8U99wyG2mb_gzx25D0-Pi7uk2e0zj5M')
            if gemini_key:
                genai.configure(api_key=gemini_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.ai_provider = 'gemini'
                logger.info("Gemini AI configured successfully")
            else:
                logger.warning("No GEMINI_API_KEY found, poster identification disabled")
                self.model = None
                self.ai_provider = None
        except Exception as e:
            logger.error(f"Failed to setup AI model: {e}")
            self.model = None
            self.ai_provider = None
    
    def load_kdrama_database(self) -> Dict[str, Dict[str, Any]]:
        """Load K-drama database."""
        return {
            "crash landing on you": {
                "title": "Crash Landing on You",
                "year": "2019-2020",
                "genre": "Romance, Comedy, Drama",
                "starring": "Hyun Bin, Son Ye-jin",
                "episodes": 16,
                "network": "tvN",
                "plot": "A South Korean heiress accidentally lands in North Korea and falls in love with a North Korean officer.",
                "rating": "9.0/10"
            },
            "squid game": {
                "title": "Squid Game",
                "year": "2021",
                "genre": "Thriller, Drama, Horror",
                "starring": "Lee Jung-jae, Park Hae-soo, Wi Ha-jun",
                "episodes": 9,
                "network": "Netflix",
                "plot": "Desperate contestants compete in childhood games for a massive cash prize, but the stakes are deadly.",
                "rating": "8.0/10"
            },
            "goblin": {
                "title": "Goblin (Guardian: The Lonely and Great God)",
                "year": "2016-2017",
                "genre": "Fantasy, Romance, Drama",
                "starring": "Gong Yoo, Kim Go-eun, Lee Dong-wook",
                "episodes": 16,
                "network": "tvN",
                "plot": "An immortal goblin seeks to end his eternal life by finding his destined bride.",
                "rating": "8.9/10"
            },
            "descendants of the sun": {
                "title": "Descendants of the Sun",
                "year": "2016",
                "genre": "Romance, Drama, Military",
                "starring": "Song Joong-ki, Song Hye-kyo",
                "episodes": 16,
                "network": "KBS2",
                "plot": "A military officer and a doctor fall in love while working in a war-torn country.",
                "rating": "8.2/10"
            },
            "hotel del luna": {
                "title": "Hotel del Luna",
                "year": "2019",
                "genre": "Fantasy, Romance, Horror",
                "starring": "IU, Yeo Jin-goo",
                "episodes": 16,
                "network": "tvN",
                "plot": "A hotel for ghosts and the living manager who runs it with her supernatural staff.",
                "rating": "8.1/10"
            },
            "kingdom": {
                "title": "Kingdom",
                "year": "2019-2020",
                "genre": "Historical, Horror, Thriller",
                "starring": "Ju Ji-hoon, Bae Doona, Ryu Seung-ryong",
                "episodes": 12,
                "network": "Netflix",
                "plot": "A crown prince investigates a mysterious plague that turns people into zombies in medieval Korea.",
                "rating": "8.3/10"
            },
            "extraordinary attorney woo": {
                "title": "Extraordinary Attorney Woo",
                "year": "2022",
                "genre": "Legal, Comedy, Drama",
                "starring": "Park Eun-bin, Kang Tae-oh",
                "episodes": 16,
                "network": "ENA",
                "plot": "A brilliant autistic lawyer navigates the legal world with her unique perspective.",
                "rating": "8.6/10"
            },
            "business proposal": {
                "title": "Business Proposal",
                "year": "2022",
                "genre": "Romance, Comedy",
                "starring": "Ahn Hyo-seop, Kim Se-jeong",
                "episodes": 12,
                "network": "SBS",
                "plot": "An employee goes on a blind date pretending to be her friend and meets her CEO.",
                "rating": "8.1/10"
            }
        }
    
    def resize_image(self, image: Image.Image, max_size: int = 1024) -> Image.Image:
        """Resize image while maintaining aspect ratio."""
        width, height = image.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return image
    
    async def analyze_poster_with_ai(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """Analyze the poster image using AI."""
        if not self.model:
            return {
                "is_kdrama_poster": False,
                "confidence": 0,
                "error": "AI model not configured"
            }
        
        try:
            # Process image
            image = Image.open(BytesIO(image_data))
            image = self.resize_image(image)
            
            prompt = """
            Analyze this image carefully and determine if it's a K-drama poster. Look for:
            1. Korean text (Hangul characters)
            2. Typical K-drama poster aesthetics and styling
            3. Korean actors or actresses
            4. Korean broadcasting network logos (tvN, KBS, SBS, MBC, Netflix Korea, etc.)
            5. Overall design elements common in Korean entertainment

            Respond ONLY in valid JSON format:
            {
                "is_kdrama_poster": true/false,
                "confidence": 0-100,
                "title": "Exact drama title if identified",
                "alternative_titles": ["Any alternative or English titles"],
                "year": "Release year if known",
                "main_actors": ["Names of actors visible or identifiable"],
                "genre": "Drama genre if determinable",
                "network": "Broadcasting network if visible",
                "korean_text": "Any Korean text visible on poster",
                "visual_style": "Description of poster style and elements",
                "reasoning": "Brief explanation of identification"
            }

            Be conservative with identification - only claim high confidence if you're very sure.
            """

            # Generate content with Gemini
            response = self.model.generate_content([prompt, image])
            response_text = response.text.strip()
            
            # Extract JSON from response
            try:
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "{" in response_text and "}" in response_text:
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    json_text = response_text[json_start:json_end]
                else:
                    raise ValueError("No JSON found in response")

                result = json.loads(json_text)
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI response: {e}")
                return {
                    "is_kdrama_poster": False,
                    "confidence": 0,
                    "error": "Failed to parse AI response"
                }

        except Exception as e:
            logger.error(f"Error analyzing image with AI: {e}")
            return {
                "is_kdrama_poster": False,
                "confidence": 0,
                "error": str(e)
            }
    
    def get_drama_info(self, title: str) -> Optional[Dict[str, Any]]:
        """Get additional drama information from local database."""
        if not title:
            return None
            
        title_lower = title.lower().strip()
        
        # Direct match
        if title_lower in self.kdrama_db:
            return self.kdrama_db[title_lower]
        
        # Partial match
        for key, info in self.kdrama_db.items():
            if key in title_lower or title_lower in key:
                return info
        
        return None
    
    def format_drama_response(self, analysis_result: Dict[str, Any]) -> str:
        """Format the drama identification response."""
        if not analysis_result.get("is_kdrama_poster", False):
            confidence = analysis_result.get("confidence", 0)
            reasoning = analysis_result.get("reasoning", "Not identified as K-drama poster")
            return f"🤔 **Not a K-drama poster**\n\nConfidence: {confidence}%\nReason: {reasoning}\n\nPlease send a clear K-drama poster image."
        
        title = analysis_result.get("title", "Unknown")
        confidence = analysis_result.get("confidence", 0)
        
        # Get additional info from database
        db_info = self.get_drama_info(title) if title != "Unknown" else None
        
        # Build response
        response = f"🎭 **K-Drama Identified!** 🎭\n\n"
        
        # Title
        response += f"**📺 Title:** {title}\n"
        
        # Alternative titles
        if analysis_result.get("alternative_titles"):
            alt_titles = ", ".join(analysis_result["alternative_titles"])
            response += f"**🏷️ Alt Titles:** {alt_titles}\n"
        
        # Year
        year = analysis_result.get("year") or (db_info.get("year") if db_info else None)
        if year:
            response += f"**📅 Year:** {year}\n"
        
        # Cast
        actors = analysis_result.get("main_actors")
        if actors and isinstance(actors, list):
            response += f"**🎭 Starring:** {', '.join(actors)}\n"
        elif db_info and db_info.get("starring"):
            response += f"**🎭 Starring:** {db_info['starring']}\n"
        
        # Genre
        genre = analysis_result.get("genre") or (db_info.get("genre") if db_info else None)
        if genre:
            response += f"**🎬 Genre:** {genre}\n"
        
        # Network
        network = analysis_result.get("network") or (db_info.get("network") if db_info else None)
        if network:
            response += f"**📡 Network:** {network}\n"
        
        # Episodes
        if db_info and db_info.get("episodes"):
            response += f"**📊 Episodes:** {db_info['episodes']}\n"
        
        # Rating
        if db_info and db_info.get("rating"):
            response += f"**⭐ Rating:** {db_info['rating']}\n"
        
        # Plot
        if db_info and db_info.get("plot"):
            response += f"\n**📖 Plot:** {db_info['plot']}\n"
        
        # Confidence and analysis details
        response += f"\n**🎯 Confidence:** {confidence}%"
        
        if analysis_result.get("korean_text"):
            response += f"\n**🔤 Korean Text:** {analysis_result['korean_text']}"
        
        if analysis_result.get("visual_style"):
            response += f"\n**🎨 Style:** {analysis_result['visual_style']}"
        
        if confidence < 70:
            response += f"\n\n⚠️ *Low confidence result. Please verify the identification.*"
        
        return response

# Initialize poster identifier
poster_identifier = PosterIdentifier()

# Existing functions

# New Poster Identification Functions

@Client.on_message(filters.command(["identify", "poster"], CMD))
async def poster_help_command(client, message):
    """Show help for poster identification."""
    help_text = """
🎭 **K-Drama Poster Identifier** 🎭

**How to use:**
📷 Send any image to identify K-drama posters

**What I can identify:**
✅ Drama title and year
✅ Main cast members  
✅ Genre and network
✅ Plot summary
✅ Confidence score

**Tips for better results:**
🎯 Use clear, high-quality poster images
🎯 Ensure Korean text is visible and readable
🎯 Full promotional posters work best
🎯 Avoid heavily cropped or blurry images

**Supported formats:** JPG, PNG, WebP

Just send me a K-drama poster and I'll do my best to identify it! 🔍
    """
    help_msg = await message.reply_text(help_text)
    await asyncio.sleep(120)
    await help_msg.delete()
    await message.delete()

@Client.on_message(filters.photo)
async def handle_poster_identification(client, message):
    """Handle image messages for poster identification."""
    if not poster_identifier.model:
        error_msg = await message.reply_text(
            "❌ **Poster identification unavailable**\n\n"
            "AI model not configured. Contact admin."
        )
        await asyncio.sleep(30)
        await error_msg.delete()
        return
    
    try:
        # Send processing message
        processing_msg = await message.reply_text(
            "🔍 **Analyzing K-drama poster...**\n\n"
            "Please wait while I identify the drama! 🎭"
        )
        
        # Download image
        image_data = await client.download_media(message.photo, in_memory=True)
        
        # Analyze with AI
        analysis_result = await poster_identifier.analyze_poster_with_ai(image_data)
        
        if not analysis_result:
            await processing_msg.edit_text(
                "❌ **Analysis Failed**\n\n"
                "Sorry, I couldn't analyze this image. Please try again with a different image."
            )
            await asyncio.sleep(30)
            await processing_msg.delete()
            return
        
        # Format and send response
        response_text = poster_identifier.format_drama_response(analysis_result)
        await processing_msg.edit_text(response_text)
        
        # Auto-delete after 5 minutes
        await asyncio.sleep(300)
        await processing_msg.delete()
        await message.delete()
        
    except Exception as e:
        logger.error(f"Error in poster identification: {e}")
        error_msg = await message.reply_text(
            "❌ **Error**\n\n"
            "Something went wrong while analyzing your image. Please try again."
        )
        await asyncio.sleep(30)
        await error_msg.delete()

@Client.on_message(filters.command("dramas", CMD))
async def list_known_dramas(client, message):
    """List dramas in the database."""
    dramas_list = "📺 **Known K-Dramas in Database:**\n\n"
    
    for i, (key, info) in enumerate(poster_identifier.kdrama_db.items(), 1):
        dramas_list += f"{i}. **{info['title']}** ({info['year']})\n"
        dramas_list += f"   ⭐ {info['rating']} | 📡 {info['network']}\n\n"
    
    dramas_list += "📷 Send me a poster image to identify more dramas!"
    
    drama_msg = await message.reply_text(dramas_list)
    await asyncio.sleep(180)  # Delete after 3 minutes
    await drama_msg.delete()
    await message.delete()

