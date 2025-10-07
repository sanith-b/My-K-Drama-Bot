from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import jwt
from datetime import datetime, timedelta
from database.ia_filterdb import get_search_results, get_file_details, Media
from database.users_chats_db import db
from info import API_SECRET_KEY, API_ACCESS_KEY, API_PORT, ADMINS
import asyncio
from logging_helper import LOGGER

app = Flask(__name__)
CORS(app)

API_TOKEN_EXPIRE_HOURS = 24

# Helper function to run async code in sync context
def run_async(coro):
    """Run async coroutine in sync context"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop if current one is running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(coro)
    except Exception as e:
        LOGGER.error(f"Error running async: {e}")
        raise
    finally:
        if not loop.is_running():
            loop.close()

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing', 'status': 401}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, API_SECRET_KEY, algorithms=["HS256"])
            request.user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired', 'status': 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token', 'status': 401}), 401
            
        return f(*args, **kwargs)
    return decorated

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing', 'status': 401}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, API_SECRET_KEY, algorithms=["HS256"])
            user_id = data['user_id']
            
            if user_id not in ADMINS:
                return jsonify({'error': 'Admin access required', 'status': 403}), 403
                
            request.user_id = user_id
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired', 'status': 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token', 'status': 401}), 401
            
        return f(*args, **kwargs)
    return decorated

# ============================================
# ROOT & HEALTH ENDPOINTS
# ============================================

@app.route('/')
def index():
    """API documentation"""
    return jsonify({
        'name': 'Telegram Bot API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'authentication': {
                'POST /api/auth/login': 'Generate authentication token',
                'GET /api/auth/verify': 'Verify token validity'
            },
            'search': {
                'GET /api/search': 'Search for files (params: q, offset, limit)',
                'GET /api/file/<file_id>': 'Get file details by ID'
            },
            'users': {
                'GET /api/users/stats': 'Get user statistics (admin)',
                'POST /api/users/<user_id>/premium': 'Manage premium access (admin)'
            },
            'maintenance': {
                'GET /api/maintenance': 'Get maintenance status (admin)',
                'POST /api/maintenance': 'Toggle maintenance mode (admin)'
            },
            'database': {
                'GET /api/db/stats': 'Get database statistics (admin)'
            },
            'health': {
                'GET /api/health': 'Health check endpoint'
            }
        },
        'authentication_required': 'Most endpoints require Bearer token authentication',
        'how_to_authenticate': {
            'step_1': 'POST /api/auth/login with user_id and api_key',
            'step_2': 'Use returned token in Authorization header: Bearer <token>'
        }
    }), 200

@app.route('/api/health')
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'uptime': 'running'
    }), 200

# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Generate authentication token"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required', 'status': 400}), 400
    
    user_id = data.get('user_id')
    api_key = data.get('api_key')
    
    if not user_id or not api_key:
        return jsonify({'error': 'user_id and api_key are required', 'status': 400}), 400
    
    # Verify API key
    if api_key != API_ACCESS_KEY:
        return jsonify({'error': 'Invalid credentials', 'status': 401}), 401
    
    # Generate token
    token = jwt.encode({
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=API_TOKEN_EXPIRE_HOURS)
    }, API_SECRET_KEY, algorithm="HS256")
    
    LOGGER.info(f"API: Token generated for user {user_id}")
    
    return jsonify({
        'success': True,
        'token': token,
        'expires_in': API_TOKEN_EXPIRE_HOURS * 3600,
        'token_type': 'Bearer'
    }), 200

@app.route('/api/auth/verify')
@token_required
def verify_token():
    """Verify if token is valid"""
    return jsonify({
        'valid': True,
        'user_id': request.user_id,
        'timestamp': datetime.utcnow().isoformat()
    }), 200

# ============================================
# FILE SEARCH ENDPOINTS
# ============================================

@app.route('/api/search')
@token_required
def search_files():
    """Search for files"""
    query = request.args.get('q', '')
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'error': 'Query parameter q is required', 'status': 400}), 400
    
    if limit > 50:
        return jsonify({'error': 'Maximum limit is 50', 'status': 400}), 400
    
    try:
        files, next_offset, total = run_async(
            get_search_results(0, query.lower(), offset=offset, filter=True)
        )
        
        results = [{
            'file_id': file.file_id,
            'file_name': file.file_name,
            'file_size': file.file_size,
            'file_type': file.file_type,
            'caption': getattr(file, 'caption', None)
        } for file in files[:limit]]
        
        LOGGER.info(f"API: Search query '{query}' returned {len(results)} results")
        
        return jsonify({
            'success': True,
            'query': query,
            'total_results': total,
            'offset': offset,
            'next_offset': next_offset if next_offset else None,
            'count': len(results),
            'results': results
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: Search error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/file/<file_id>')
@token_required
def get_file(file_id):
    """Get file details by ID"""
    try:
        files = run_async(get_file_details(file_id))
        
        if not files:
            return jsonify({'error': 'File not found', 'status': 404}), 404
        
        file = files[0]
        
        result = {
            'success': True,
            'file': {
                'file_id': file.file_id,
                'file_name': file.file_name,
                'file_size': file.file_size,
                'file_type': file.file_type,
                'caption': getattr(file, 'caption', None)
            }
        }
        
        LOGGER.info(f"API: File details retrieved for {file_id}")
        return jsonify(result), 200
        
    except Exception as e:
        LOGGER.error(f"API: Get file error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

# ============================================
# USER MANAGEMENT ENDPOINTS
# ============================================

@app.route('/api/users/stats')
@admin_required
def get_user_stats():
    """Get user statistics"""
    try:
        total_users = run_async(db.total_users_count())
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'timestamp': datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: User stats error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/users/<int:user_id>/premium', methods=['POST'])
@admin_required
def manage_premium(user_id):
    """Grant or revoke premium access"""
    data = request.get_json()
    action = data.get('action', 'grant')
    days = data.get('days', 30)
    
    if action not in ['grant', 'revoke']:
        return jsonify({'error': 'Action must be grant or revoke', 'status': 400}), 400
    
    try:
        if action == 'grant':
            run_async(db.add_premium(user_id, days))
            message = f'Premium granted for {days} days'
        else:
            run_async(db.remove_premium(user_id))
            message = 'Premium revoked'
        
        LOGGER.info(f"API: {message} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': message,
            'user_id': user_id
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: Premium management error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

# ============================================
# MAINTENANCE ENDPOINTS
# ============================================

@app.route('/api/maintenance')
@admin_required
def get_maintenance_status():
    """Get maintenance mode status"""
    try:
        # Assuming bot_id is first admin
        bot_id = ADMINS[0] if ADMINS else 0
        status = run_async(db.get_maintenance_status(bot_id))
        
        return jsonify({
            'success': True,
            'maintenance_mode': status,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: Maintenance status error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/maintenance', methods=['POST'])
@admin_required
def toggle_maintenance():
    """Toggle maintenance mode"""
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    try:
        bot_id = ADMINS[0] if ADMINS else 0
        run_async(db.set_maintenance(bot_id, enabled))
        
        LOGGER.info(f"API: Maintenance mode set to {enabled}")
        
        return jsonify({
            'success': True,
            'maintenance_mode': enabled,
            'message': f'Maintenance mode {"enabled" if enabled else "disabled"}'
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: Toggle maintenance error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

# ============================================
# DATABASE STATS ENDPOINTS
# ============================================

@app.route('/api/db/stats')
@admin_required
def get_db_stats():
    """Get database statistics"""
    try:
        total_files = run_async(Media.count_documents({}))
        
        return jsonify({
            'success': True,
            'database': {
                'total_files': total_files,
                'timestamp': datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        LOGGER.error(f"API: DB stats error - {e}")
        return jsonify({'error': str(e), 'status': 500}), 500

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'status': 404,
        'message': 'The requested endpoint does not exist'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'status': 500,
        'message': 'An unexpected error occurred'
    }), 500

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Method not allowed',
        'status': 405,
        'message': 'The HTTP method is not allowed for this endpoint'
    }), 405

# ============================================
# RUN API SERVER
# ============================================

def run_api():
    """Run Flask API server"""
    try:
        LOGGER.info(f"Starting API server on port {API_PORT}...")
        app.run(host='0.0.0.0', port=API_PORT, debug=False, use_reloader=False)
    except Exception as e:
        LOGGER.error(f"Failed to start API server: {e}")
