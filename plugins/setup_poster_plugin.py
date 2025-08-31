#!/usr/bin/env python3
"""
FREE K-Drama Poster Identification Setup Script
This script helps you set up the poster identification plugin with zero cost!
"""

import os
import sys
import subprocess
import platform

def install_tesseract():
    """
    Install Tesseract OCR based on operating system
    """
    system = platform.system().lower()
    
    print("📦 Installing Tesseract OCR (FREE OCR engine)...")
    
    if system == "linux":
        print("🐧 Detected Linux - Installing via apt-get...")
        try:
            # Update package list
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            
            # Install Tesseract and Korean language pack
            subprocess.run([
                "sudo", "apt-get", "install", "-y", 
                "tesseract-ocr", "tesseract-ocr-kor", "tesseract-ocr-eng"
            ], check=True)
            
            print("✅ Tesseract installed successfully!")
            return True
            
        except subprocess.CalledProcessError:
            print("❌ Failed to install Tesseract via apt-get")
            print("💡 Try manual installation:")
            print("   sudo apt-get install tesseract-ocr tesseract-ocr-kor")
            return False
            
    elif system == "darwin":  # macOS
        print("🍎 Detected macOS - Installing via Homebrew...")
        try:
            # Install via Homebrew
            subprocess.run(["brew", "install", "tesseract", "tesseract-lang"], check=True)
            print("✅ Tesseract installed successfully!")
            return True
            
        except subprocess.CalledProcessError:
            print("❌ Failed to install Tesseract via Homebrew")
            print("💡 Install Homebrew first: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            print("   Then run: brew install tesseract tesseract-lang")
            return False
            
    elif system == "windows":
        print("🪟 Detected Windows - Manual installation required...")
        print("📥 Please download and install Tesseract manually:")
        print("   1. Go to: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   2. Download the latest Windows installer")
        print("   3. Run the installer")
        print("   4. Make sure to install Korean language pack")
        print("   5. Add Tesseract to your PATH environment variable")
        print("\n⏳ Press Enter after installation is complete...")
        input()
        return True
    
    else:
        print(f"❓ Unknown operating system: {system}")
        print("📖 Please install Tesseract manually for your system")
        return False

def install_python_packages():
    """
    Install required Python packages
    """
    print("🐍 Installing Python packages...")
    
    packages = [
        "Pillow>=9.0.0",
        "pytesseract>=0.3.10", 
        "requests>=2.28.0",
        "python-dotenv>=0.19.0",
        "opencv-python>=4.7.0",
        "numpy>=1.21.0"
    ]
    
    try:
        for package in packages:
            print(f"   Installing {package}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True)
        
        print("✅ All Python packages installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        print("💡 Try installing manually:")
        print("   pip install Pillow pytesseract requests python-dotenv opencv-python numpy")
        return False

def setup_free_api_keys():
    """
    Guide user through setting up free API keys
    """
    print("\n🔑 Setting up FREE API Keys (Optional but Recommended)")
    print("=" * 60)
    
    # TMDB Setup
    print("\n1. 🎬 TMDB (The Movie Database) - COMPLETELY FREE")
    print("   📝 What it provides: Drama metadata, posters, ratings")
    print("   🔗 Sign up at: https://www.themoviedb.org/signup")
    print("   ⚙️  Get API key at: https://www.themoviedb.org/settings/api")
    
    tmdb_key = input("   Enter your TMDB API key (or press Enter to skip): ").strip()
    
    # OMDB Setup  
    print("\n2. 🎭 OMDB (Open Movie Database) - FREE 1000 requests/day")
    print("   📝 What it provides: Additional ratings and plot info")
    print("   🔗 Get free key at: http://www.omdbapi.com/apikey.aspx")
    
    omdb_key = input("   Enter your OMDB API key (or press Enter to skip): ").strip()
    
    # Create .env file
    env_content = f"""# K-Drama Bot FREE API Configuration
# All these APIs are completely FREE to use!

# TMDB - Free forever, no limits
TMDB_API_KEY={tmdb_key}

# OMDB - Free 1000 requests per day  
OMDB_API_KEY={omdb_key}

# Note: The plugin works perfectly WITHOUT these keys too!
# It uses the built-in database and free local OCR.
"""
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        print("💡 Create it manually and add the API keys above")

def test_installation():
    """
    Test if everything is working
    """
    print("\n🧪 Testing installation...")
    
    try:
        # Test imports
        print("   Testing imports...")
        from PIL import Image
        import pytesseract
        import requests
        print("   ✅ All imports successful!")
        
        # Test Tesseract
        print("   Testing Tesseract OCR...")
        test_image = Image.new('RGB', (200, 100), color='white')
        pytesseract.image_to_string(test_image)
        print("   ✅ Tesseract OCR working!")
        
        # Test plugin
        print("   Testing plugin...")
        from poster_identification import PosterIdentification
        plugin = PosterIdentification()
        health = plugin.health_check()
        
        if health['builtin_database']:
            print("   ✅ Built-in database loaded!")
        
        print("\n🎉 Installation test completed successfully!")
        print("🚀 Your poster identification plugin is ready to use!")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("   💡 Try reinstalling packages: pip install -r requirements.txt")
        return False
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def main():
    """
    Main setup function
    """
    print("🎬 K-Drama Poster Identification Plugin Setup")
    print("=" * 50)
    print("This setup is 100% FREE! No paid APIs required.")
    print()
    
    # Step 1: Install Tesseract
    print("STEP 1: Installing Tesseract OCR")
    print("-" * 30)
    tesseract_ok = install_tesseract()
    
    # Step 2: Install Python packages
    print("\nSTEP 2: Installing Python Packages")
    print("-" * 35)
    packages_ok = install_python_packages()
    
    # Step 3: Setup API keys (optional)
    print("\nSTEP 3: Setting up Free API Keys (Optional)")
    print("-" * 45)
    setup_free_api_keys()
    
    # Step 4: Test installation
    print("\nSTEP 4: Testing Installation")
    print("-" * 28)
    test_ok = test_installation()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 SETUP SUMMARY")
    print("=" * 50)
    print(f"Tesseract OCR: {'✅ Working' if tesseract_ok else '❌ Needs manual setup'}")
    print(f"Python Packages: {'✅ Installed' if packages_ok else '❌ Failed'}")
    print(f"Plugin Test: {'✅ Passed' if test_ok else '❌ Failed'}")
    
    if tesseract_ok and packages_ok and test_ok:
        print("\n🎉 SETUP COMPLETE!")
        print("🚀 Your poster identification plugin is ready!")
        print("\n📖 Usage:")
        print("   1. Place poster_identification.py in your plugins/ folder")
        print("   2. Upload a K-drama poster image")
        print("   3. Type: !identify")
        print("   4. Get instant drama information!")
    else:
        print("\n⚠️  Setup incomplete. Please fix the issues above.")
    
    print("\n💡 Quick Test:")
    print("   python setup_poster_plugin.py test")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_plugin()
    else:
        main()
