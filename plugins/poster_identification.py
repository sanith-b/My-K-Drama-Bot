import os
import requests
import base64
import json
import re
from PIL import Image
import pytesseract
from io import BytesIO
import difflib
from typing import Dict, List, Optional, Tuple

class PosterIdentification:
    def __init__(self):
        self.name = 'poster_identification'
        self.description = 'Identify K-dramas from poster images or screenshots using FREE APIs'
        
        # Free API configurations
        self.config = {
            # All these are FREE to use!
            'jikan_api': 'https://api.jikan.moe/v4',  # Free anime/drama API
            'omdb_api_key': os.getenv('OMDB_API_KEY', '211afadf'),  # Free 1000 requests/day
            'tmdb_api_key': os.getenv('90dde61a7cf8339a2cff5d805d5597a9', ''),  # Free API key
        }
        
        # Built-in comprehensive K-drama database (FREE!)
        self.kdrama_database = [
            {
                "title": "Crash Landing on You",
                "korean_title": "사랑의 불시착",
                "year": 2019,
                "network": "tvN",
                "episodes": 16,
                "genre": ["Romance", "Comedy", "Drama"],
                "rating": 9.0,
                "cast": ["Hyun Bin", "Son Ye-jin", "Seo Ji-hye", "Kim Jung-hyun"],
                "keywords": ["north korea", "paragliding", "chaebol", "military"]
            },
            {
                "title": "Hotel del Luna",
                "korean_title": "호텔 델루나",
                "year": 2019,
                "network": "tvN",
                "episodes": 16,
                "genre": ["Fantasy", "Romance", "Horror"],
                "rating": 8.8,
                "cast": ["IU", "Yeo Jin-goo", "P.O", "Kang Mi-na"],
                "keywords": ["hotel", "ghost", "afterlife", "spirits", "ceo"]
            },
            {
                "title": "Squid Game",
                "korean_title": "오징어 게임",
                "year": 2021,
                "network": "Netflix",
                "episodes": 9,
                "genre": ["Thriller", "Drama", "Action"],
                "rating": 8.0,
                "cast": ["Lee Jung-jae", "Park Hae-soo", "Jung Ho-yeon", "O Yeong-su"],
                "keywords": ["game", "survival", "debt", "competition", "childhood"]
            },
            {
                "title": "Goblin",
                "korean_title": "쓸쓸하고 찬란하神-도깨비",
                "year": 2016,
                "network": "tvN",
                "episodes": 16,
                "genre": ["Fantasy", "Romance", "Drama"],
                "rating": 9.2,
                "cast": ["Gong Yoo", "Kim Go-eun", "Lee Dong-wook", "Yoo In-na"],
                "keywords": ["immortal", "grim reaper", "bride", "sword", "supernatural"]
            },
            {
                "title": "Descendants of the Sun",
                "korean_title": "태양의 후예",
                "year": 2016,
                "network": "KBS",
                "episodes": 16,
                "genre": ["Romance", "Drama", "Action"],
                "rating": 8.7,
                "cast": ["Song Joong-ki", "Song Hye-kyo", "Jin Goo", "Kim Ji-won"],
                "keywords": ["military", "doctor", "peacekeeping", "urk", "earthquake"]
            },
            {
                "title": "Itaewon Class",
                "korean_title": "이태원 클라쓰",
                "year": 2020,
                "network": "JTBC",
                "episodes": 16,
                "genre": ["Drama", "Romance"],
                "rating": 8.2,
                "cast": ["Park Seo-joon", "Kim Da-mi", "Yoo Jae-myung", "Kwon Na-ra"],
                "keywords": ["restaurant", "revenge", "itaewon", "business", "youth"]
            },
            {
                "title": "Kingdom",
                "korean_title": "킹덤",
                "year": 2019,
                "network": "Netflix",
                "episodes": 12,
                "genre": ["Historical", "Horror", "Thriller"],
                "rating": 8.3,
                "cast": ["Ju Ji-hoon", "Bae Doona", "Ryu Seung-ryong", "Kim Sang-ho"],
                "keywords": ["zombie", "joseon", "crown prince", "plague", "political"]
            },
            {
                "title": "Reply 1988",
                "korean_title": "응답하라 1988",
                "year": 2015,
                "network": "tvN",
                "episodes": 20,
                "genre": ["Romance", "Comedy", "Drama", "Family"],
                "rating": 9.1,
                "cast": ["Lee Hye-ri", "Park Bo-gum", "Go Kyung-pyo", "Lee Dong-hwi"],
                "keywords": ["1988", "neighborhood", "family", "friendship", "nostalgia"]
            },
            {
                "title": "What's Wrong with Secretary Kim",
                "korean_title": "김비서가 왜 그럴까",
                "year": 2018,
                "network": "tvN",
                "episodes": 16,
                "genre": ["Romance", "Comedy"],
                "rating": 8.5,
                "cast": ["Park Seo-joon", "Park Min-young", "Lee Tae-hwan", "Pyo Ye-jin"],
                "keywords": ["secretary", "ceo", "office", "romance", "workplace"]
            },
            {
                "title": "Business Proposal",
                "korean_title": "사내맞선",
                "year": 2022,
                "network": "SBS",
                "episodes": 12,
                "genre": ["Romance", "Comedy"],
                "rating": 8.1,
                "cast": ["Ahn Hyo-seop", "Kim Se-jeong", "Kim Min-kyu", "Seol In-ah"],
                "keywords": ["fake dating", "ceo", "employee", "blind date", "chaebol"]
            }
            # Add more dramas as needed
        ]
        
        # Korean drama networks and streaming platforms
        self.networks = [
            'SBS', 'KBS', 'MBC', 'tvN', 'JTBC', 'OCN', 'Netflix', 'Viki', 
            'Disney+', 'Wavve', 'Tving', 'Kakao TV'
        ]
        
        # Korean drama keywords for validation
        self.kdrama_keywords = [
            '드라마', 'drama', 'kdrama', 'korean', '한국', '회', 'episode', 
            '부작', '시리즈', 'series', '방송', 'broadcast', '출연', 'starring'
        ]

    def identify_poster(self, image_path_or_bytes, filename="poster.jpg"):
        """
        Main function to identify K-drama from poster/screenshot
        """
        try:
            print(f"🔍 Analyzing image: {filename}")
            
            # Step 1: Extract text using free OCR
            extracted_text = self.extract_text_free_ocr(image_path_or_bytes)
            print(f"📝 Extracted text: {extracted_text[:100]}...")
            
            # Step 2: Analyze extracted text
            search_terms = self.extract_search_terms(extracted_text)
            print(f"🔎 Search terms: {search_terms}")
            
            # Step 3: Search drama database
            matches = self.search_drama_database(search_terms, extracted_text)
            
            # Step 4: Try free APIs for additional data
            enhanced_matches = self.enhance_with_free_apis(matches)
            
            # Step 5: Format response
            return self.format_response(enhanced_matches, extracted_text)
            
        except Exception as e:
            print(f"❌ Error identifying image: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to analyze image: {str(e)}',
                'suggestions': [
                    'Make sure the image is clear and readable',
                    'Try a different image format (JPG, PNG)',
                    'Check if it\'s actually a K-drama poster'
                ]
            }

    def extract_text_free_ocr(self, image_input):
        """
        Extract text using FREE Tesseract OCR (no API keys needed!)
        """
        try:
            # Handle different input types
            if isinstance(image_input, str):
                # File path
                image = Image.open(image_input)
            elif isinstance(image_input, bytes):
                # Bytes data
                image = Image.open(BytesIO(image_input))
            else:
                # PIL Image
                image = image_input
            
            # Optimize image for OCR
            image = self.preprocess_image_for_ocr(image)
            
            # Extract text with both English and Korean
            custom_config = r'--oem 3 --psm 6 -l eng+kor'
            extracted_text = pytesseract.image_to_string(image, config=custom_config)
            
            return extracted_text.strip()
            
        except Exception as e:
            print(f"OCR error: {str(e)}")
            # Fallback: try English only
            try:
                extracted_text = pytesseract.image_to_string(image, lang='eng')
                return extracted_text.strip()
            except:
                return ""

    def preprocess_image_for_ocr(self, image):
        """
        Optimize image for better OCR results
        """
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large (OCR works better on medium-sized images)
        max_size = 1500
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Enhance contrast for better text detection
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        return image

    def extract_search_terms(self, text):
        """
        Extract relevant search terms from OCR text
        """
        if not text:
            return []
        
        terms = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) < 2:
                continue
                
            # Korean title patterns
            korean_matches = re.findall(r'[가-힣]{2,}', line)
            terms.extend(korean_matches)
            
            # English title patterns
            english_matches = re.findall(r'[A-Za-z][A-Za-z\s]{2,}[A-Za-z]', line)
            terms.extend([match.strip() for match in english_matches])
            
            # Network detection
            for network in self.networks:
                if network.lower() in line.lower():
                    terms.append(network)
        
        # Clean and deduplicate
        clean_terms = []
        for term in terms:
            term = re.sub(r'[^\w\s가-힣]', '', term).strip()
            if len(term) > 2 and term not in clean_terms:
                clean_terms.append(term)
        
        return clean_terms[:10]  # Limit to top 10 terms

    def search_drama_database(self, search_terms, full_text):
        """
        Search the built-in K-drama database
        """
        matches = []
        
        for drama in self.kdrama_database:
            confidence = self.calculate_confidence(drama, search_terms, full_text)
            
            if confidence > 0.1:  # Minimum threshold
                drama_copy = drama.copy()
                drama_copy['confidence'] = confidence
                drama_copy['source'] = 'builtin_database'
                matches.append(drama_copy)
        
        # Sort by confidence
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches[:5]  # Return top 5 matches

    def calculate_confidence(self, drama, search_terms, full_text):
        """
        Calculate confidence score for drama match
        """
        confidence = 0.0
        text_lower = full_text.lower()
        
        # Title matching (highest weight)
        title_match = difflib.SequenceMatcher(None, 
            drama['title'].lower(), text_lower).ratio()
        korean_title_match = 0
        
        if drama['korean_title'] in full_text:
            korean_title_match = 0.9
        
        confidence += max(title_match, korean_title_match) * 0.4
        
        # Year matching
        if str(drama['year']) in full_text:
            confidence += 0.2
        
        # Network matching
        if drama['network'].lower() in text_lower:
            confidence += 0.15
        
        # Cast matching
        for actor in drama['cast']:
            if actor.lower() in text_lower:
                confidence += 0.1
                break
        
        # Keyword matching
        for keyword in drama['keywords']:
            if keyword.lower() in text_lower:
                confidence += 0.05
        
        # Search terms matching
        for term in search_terms:
            if term.lower() in drama['title'].lower() or term in drama['korean_title']:
                confidence += 0.1
        
        return min(confidence, 1.0)

    def enhance_with_free_apis(self, matches):
        """
        Enhance results using free APIs (TMDB, OMDB)
        """
        enhanced_matches = []
        
        for match in matches:
            enhanced_match = match.copy()
            
            # Try to get additional info from TMDB (free)
            tmdb_info = self.search_tmdb_free(match['title'], match['year'])
            if tmdb_info:
                enhanced_match.update(tmdb_info)
            
            # Try OMDB (free tier)
            omdb_info = self.search_omdb_free(match['title'], match['year'])
            if omdb_info:
                enhanced_match.update(omdb_info)
            
            enhanced_matches.append(enhanced_match)
        
        return enhanced_matches

    def search_tmdb_free(self, title, year):
        """
        Search TMDB free API for additional drama info
        """
        if not self.config['tmdb_api_key']:
            return {}
        
        try:
            # TMDB free API search
            url = "https://api.themoviedb.org/3/search/tv"
            params = {
                'api_key': self.config['tmdb_api_key'],
                'query': title,
                'first_air_date_year': year
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    result = data['results'][0]
                    return {
                        'tmdb_id': result['id'],
                        'overview': result.get('overview', ''),
                        'poster_path': f"https://image.tmdb.org/t/p/w500{result.get('poster_path', '')}",
                        'backdrop_path': f"https://image.tmdb.org/t/p/w500{result.get('backdrop_path', '')}",
                        'popularity': result.get('popularity', 0),
                        'vote_average': result.get('vote_average', 0)
                    }
        except Exception as e:
            print(f"TMDB search error: {e}")
        
        return {}

    def search_omdb_free(self, title, year):
        """
        Search OMDB free API (1000 requests/day)
        """
        if not self.config['omdb_api_key']:
            return {}
        
        try:
            url = "http://www.omdbapi.com/"
            params = {
                'apikey': self.config['omdb_api_key'],
                't': title,
                'y': year,
                'type': 'series'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'True':
                    return {
                        'omdb_rating': data.get('imdbRating', 'N/A'),
                        'plot': data.get('Plot', ''),
                        'awards': data.get('Awards', ''),
                        'runtime': data.get('Runtime', '')
                    }
        except Exception as e:
            print(f"OMDB search error: {e}")
        
        return {}

    def identify_from_url(self, image_url):
        """
        Download and identify image from URL
        """
        try:
            response = requests.get(image_url, timeout=30)
            if response.status_code == 200:
                image_bytes = response.content
                return self.identify_poster(image_bytes, "downloaded_image.jpg")
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to download image: {str(e)}'
            }

    def reverse_image_search_free(self, image_bytes):
        """
        Free reverse image search using Google (limited but free)
        """
        try:
            # This is a basic implementation - you could enhance with other free services
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Use free reverse search services (like TinEye API free tier)
            # For now, return empty - you can integrate free services here
            return []
            
        except Exception as e:
            print(f"Reverse search error: {e}")
            return []

    def format_response(self, matches, extracted_text):
        """
        Format the identification response
        """
        if not matches:
            return {
                'success': False,
                'message': "❌ Couldn't identify this K-drama poster/screenshot.",
                'suggestions': [
                    "Make sure the image shows a clear K-drama poster",
                    "Try uploading a higher quality image", 
                    "Check if the drama is popular/well-known",
                    "Try typing the drama name if visible in the image"
                ],
                'extracted_text': extracted_text[:200] + '...' if len(extracted_text) > 200 else extracted_text
            }

        top_match = matches[0]
        confidence = top_match.get('confidence', 0)
        
        # Build response message
        if confidence > 0.8:
            message = "✅ **High Confidence Match!**\n\n"
        elif confidence > 0.5:
            message = "🤔 **Possible Match:**\n\n"
        else:
            message = "❓ **Low Confidence - Please Verify:**\n\n"

        # Main drama info
        message += f"**{top_match['title']}**"
        
        if top_match.get('korean_title') and top_match['korean_title'] != top_match['title']:
            message += f" ({top_match['korean_title']})"
        
        message += "\n\n"
        
        # Details
        if top_match.get('year'):
            message += f"📅 **Year:** {top_match['year']}\n"
        if top_match.get('network'):
            message += f"📺 **Network:** {top_match['network']}\n"
        if top_match.get('episodes'):
            message += f"🎬 **Episodes:** {top_match['episodes']}\n"
        if top_match.get('rating'):
            message += f"⭐ **Rating:** {top_match['rating']}/10\n"
        if top_match.get('genre'):
            genres = top_match['genre'] if isinstance(top_match['genre'], list) else [top_match['genre']]
            message += f"🎭 **Genre:** {', '.join(genres)}\n"
        if top_match.get('cast'):
            cast_list = top_match['cast'][:4]  # Show first 4 actors
            message += f"👥 **Cast:** {', '.join(cast_list)}\n"
        
        # Additional info from APIs
        if top_match.get('overview'):
            message += f"\n📖 **Synopsis:** {top_match['overview'][:150]}...\n"
        
        if top_match.get('poster_path'):
            message += f"\n🖼️ **Poster:** {top_match['poster_path']}\n"

        # Alternative matches
        if len(matches) > 1:
            message += "\n**🔄 Other Possible Matches:**\n"
            for i, match in enumerate(matches[1:3], 2):  # Show 2 alternatives
                message += f"{i}. {match['title']}"
                if match.get('year'):
                    message += f" ({match['year']})"
                message += "\n"
        
        # Confidence indicator
        confidence_emoji = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.5 else "🔴"
        message += f"\n{confidence_emoji} **Confidence:** {confidence:.1%}"

        return {
            'success': True,
            'message': message,
            'primary_match': top_match,
            'alternative_matches': matches[1:],
            'confidence': confidence,
            'extracted_text': extracted_text
        }

    def get_commands(self):
        """
        Return available bot commands
        """
        return {
            'identify': {
                'description': 'Identify K-drama from poster/screenshot image',
                'usage': 'Upload an image and use: !identify',
                'function': self.handle_identify_command
            },
            'poster_help': {
                'description': 'Get help with poster identification',
                'usage': '!poster_help',
                'function': self.handle_help_command
            },
            'drama_search': {
                'description': 'Search for drama by name',
                'usage': '!drama_search <drama name>',
                'function': self.handle_search_command
            }
        }

    async def handle_identify_command(self, message, args, image_attachment=None):
        """
        Handle the !identify command
        """
        if not image_attachment:
            return ("Please upload an image of a K-drama poster or screenshot along with the !identify command.\n\n"
                   "**Example:**\n"
                   "1. Upload image\n"
                   "2. Type: `!identify`\n"
                   "3. Wait for analysis results!")
        
        try:
            # Download image from attachment
            response = requests.get(image_attachment['url'], timeout=30)
            if response.status_code != 200:
                return "❌ Failed to download the image. Please try again."
            
            image_bytes = response.content
            
            # Check file size (limit to 20MB)
            if len(image_bytes) > 20 * 1024 * 1024:
                return "❌ Image file too large. Please upload an image smaller than 20MB."
            
            # Identify the drama
            result = self.identify_poster(image_bytes, image_attachment.get('filename', 'image.jpg'))
            
            return result['message']
            
        except Exception as e:
            print(f"Command execution error: {e}")
            return "❌ Failed to process the image. Please try again with a clear K-drama poster or screenshot."

    async def handle_help_command(self, message, args):
        """
        Handle the !poster_help command
        """
        help_text = """**🎬 K-Drama Poster Identification Help**

**🚀 How to use:**
1. Upload a K-drama poster or screenshot image
2. Use the command `!identify`
3. Wait for the bot to analyze and identify the drama

**📸 What images work best:**
✅ Official drama posters
✅ Clear episode screenshots  
✅ Images with visible Korean or English text
✅ Promotional materials
✅ Behind-the-scenes photos with drama elements

**🎯 Supported image formats:**
• JPG/JPEG
• PNG  
• WebP
• GIF (first frame)

**💡 Tips for better results:**
• Use clear, well-lit images
• Make sure text is readable
• Avoid heavily edited or filtered images
• Try different angles if first attempt fails

**🔧 Available commands:**
• `!identify` - Identify drama from uploaded image
• `!drama_search <name>` - Search for drama by name
• `!poster_help` - Show this help message

**🆓 Completely FREE:** This plugin uses free OCR and built-in database - no API costs!

**🐛 Having issues?** Make sure your image is clear and shows a K-drama poster or screenshot."""

        return help_text

    async def handle_search_command(self, message, args):
        """
        Handle the !drama_search command
        """
        if not args:
            return "Please provide a drama name to search for.\n**Usage:** `!drama_search Hotel del Luna`"
        
        search_query = ' '.join(args).strip()
        matches = []
        
        # Search in built-in database
        for drama in self.kdrama_database:
            title_similarity = difflib.SequenceMatcher(None, 
                drama['title'].lower(), search_query.lower()).ratio()
            korean_similarity = difflib.SequenceMatcher(None,
                drama['korean_title'], search_query).ratio()
            
            similarity = max(title_similarity, korean_similarity)
            
            if similarity > 0.3:  # 30% similarity threshold
                drama_copy = drama.copy()
                drama_copy['confidence'] = similarity
                matches.append(drama_copy)
        
        if not matches:
            return f"❌ No matches found for '{search_query}'. Try searching with different keywords or check spelling."
        
        # Sort by similarity
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Format response
        if len(matches) == 1:
            match = matches[0]
            response = f"**{match['title']}** ({match['korean_title']})\n"
            response += f"📅 {match['year']} • 📺 {match['network']} • 🎬 {match['episodes']} episodes\n"
            response += f"⭐ Rating: {match['rating']}/10\n"
            response += f"🎭 Genre: {', '.join(match['genre'])}\n"
            response += f"👥 Cast: {', '.join(match['cast'][:3])}"
            return response
        else:
            response = f"**🔍 Found {len(matches)} matches for '{search_query}':**\n\n"
            for i, match in enumerate(matches[:5], 1):
                response += f"{i}. **{match['title']}** ({match['year']}) - {match['network']}\n"
            return response

    def setup_free_apis(self):
        """
        Setup instructions for free APIs
        """
        setup_info = {
            'tmdb': {
                'name': 'The Movie Database (TMDB)',
                'url': 'https://www.themoviedb.org/settings/api',
                'free_tier': 'Completely free with registration',
                'setup': [
                    '1. Create account at themoviedb.org',
                    '2. Go to Settings > API',
                    '3. Request API key (instant approval)',
                    '4. Add TMDB_API_KEY to environment variables'
                ]
            },
            'omdb': {
                'name': 'Open Movie Database (OMDB)',
                'url': 'http://www.omdbapi.com/apikey.aspx',
                'free_tier': '1,000 requests per day',
                'setup': [
                    '1. Visit omdbapi.com',
                    '2. Request free API key',
                    '3. Verify email',
                    '4. Add OMDB_API_KEY to environment variables'
                ]
            },
            'tesseract': {
                'name': 'Tesseract OCR',
                'url': 'https://github.com/tesseract-ocr/tesseract',
                'free_tier': 'Completely free, runs locally',
                'setup': [
                    '1. Install Tesseract: sudo apt-get install tesseract-ocr',
                    '2. Install Korean language pack: sudo apt-get install tesseract-ocr-kor',
                    '3. Install Python package: pip install pytesseract',
                    '4. No API key needed!'
                ]
            }
        }
        
        return setup_info

    def health_check(self):
        """
        Check plugin health and API status
        """
        status = {
            'builtin_database': True,
            'tesseract_ocr': self.check_tesseract(),
            'tmdb_api': bool(self.config['tmdb_api_key']),
            'omdb_api': bool(self.config['omdb_api_key']),
            'overall_status': 'ready'
        }
        
        return status

    def check_tesseract(self):
        """
        Check if Tesseract is installed and working
        """
        try:
            # Test with a simple image
            test_image = Image.new('RGB', (100, 50), color='white')
            pytesseract.image_to_string(test_image)
            return True
        except Exception as e:
            print(f"Tesseract check failed: {e}")
            return False

# Bot integration class
class PosterIdentificationBot:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.plugin = PosterIdentification()
        self.setup_commands()

    def setup_commands(self):
        """
        Register all commands with the bot
        """
        commands = self.plugin.get_commands()
        
        for command_name, command_config in commands.items():
            # Register command with bot (adjust this based on your bot framework)
            self.bot.add_command(command_name, command_config['function'])
        
        print("✅ Poster Identification Plugin commands registered!")

    async def handle_image_message(self, message):
        """
        Auto-detect when someone uploads an image and asks about it
        """
        # Check if message has image attachment and drama-related question
        if (hasattr(message, 'attachments') and message.attachments and 
            any(keyword in message.content.lower() for keyword in 
                ['what drama', 'which drama', 'identify', 'what show', 'what is this'])):
            
            image_attachment = None
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_attachment = {
                        'url': attachment.url,
                        'filename': attachment.filename
                    }
                    break
            
            if image_attachment:
                result = await self.plugin.handle_identify_command(message, [], image_attachment)
                await message.reply(result)

# Main plugin initialization function
def init_plugin(bot):
    """
    Initialize the poster identification plugin
    """
    try:
        # Create plugin instance
        plugin_bot = PosterIdentificationBot(bot)
        
        # Setup health check
        health = plugin_bot.plugin.health_check()
        
        print("🎬 Poster Identification Plugin Status:")
        print(f"   📊 Built-in Database: {'✅' if health['builtin_database'] else '❌'}")
        print(f"   🔤 Tesseract OCR: {'✅' if health['tesseract_ocr'] else '❌'}")
        print(f"   🎞️  TMDB API: {'✅' if health['tmdb_api'] else '⚠️  (Optional)'}")
        print(f"   🎬 OMDB API: {'✅' if health['omdb_api'] else '⚠️  (Optional)'}")
        
        if not health['tesseract_ocr']:
            print("⚠️  WARNING: Tesseract OCR not found. Install with:")
            print("   Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-kor")
            print("   Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            print("   macOS: brew install tesseract tesseract-lang")
        
        print("✅ Poster Identification Plugin loaded successfully!")
        return plugin_bot
        
    except Exception as e:
        print(f"❌ Failed to load Poster Identification Plugin: {e}")
        return None

# Example usage and testing functions
def test_plugin():
    """
    Test the plugin with sample data
    """
    plugin = PosterIdentification()
    
    # Test with sample text (simulating OCR result)
    sample_texts = [
        "Hotel del Luna 호텔 델루나 tvN 2019 IU Yeo Jin-goo",
        "사랑의 불시착 Crash Landing on You tvN 2019",
        "Squid Game 오징어 게임 Netflix 2021"
    ]
    
    print("🧪 Testing poster identification...")
    
    for i, text in enumerate(sample_texts, 1):
        print(f"\nTest {i}: {text}")
        terms = plugin.extract_search_terms(text)
        matches = plugin.search_drama_database(terms, text)
        result = plugin.format_response(matches, text)
        
        print(f"Result: {result['success']}")
        if result['success']:
            print(f"Top Match: {result['primary_match']['title']} (confidence: {result['confidence']:.2f})")

if __name__ == "__main__":
    # Run tests when script is executed directly
    test_plugin()

"""
INSTALLATION INSTRUCTIONS:

1. **Install Dependencies:**
   ```bash
   pip install Pillow pytesseract requests difflib
   ```

2. **Install Tesseract OCR:**
   - Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-kor`
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - macOS: `brew install tesseract tesseract-lang`

3. **Optional Free API Keys (.env file):**
   ```env
   # TMDB (Free forever)
   TMDB_API_KEY=your_tmdb_api_key_here
   
   # OMDB (Free 1000 requests/day)
   OMDB_API_KEY=your_omdb_api_key_here
   ```

4. **Integration with your bot:**
   ```python
   # In your main bot file
   from plugins.poster_identification import init_plugin
   
   # Initialize the plugin
   poster_plugin = init_plugin(your_bot_instance)
   ```

5. **Usage:**
   - Upload K-drama poster/screenshot
   - Type: `!identify`
   - Get instant drama information!

FEATURES:
✅ 100% FREE to use
✅ Works offline with built-in database  
✅ Supports Korean and English text
✅ Multiple confidence levels
✅ Auto-detection of drama-related images
✅ Comprehensive drama information
✅ Easy to extend with more dramas

SUPPORTED PLATFORMS:
• Discord bots
• Telegram bots  
• Slack bots
• Custom Python applications
"""
