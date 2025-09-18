# backend/app.py
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity, get_jwt
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId # For working with MongoDB _id

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb+srv://kachhivikas1:ADMIN1234@cluster.bwpehug.mongodb.net//community_complaint_portal_IARS")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super_secret_fallback_key_for_jwt_dev_only")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1) # Token expires in 1 hour

mongo = PyMongo(app)
jwt = JWTManager(app)
CORS(app) # Enable CORS for all routes by default

# Define MongoDB collections
users_collection = mongo.db.users
issues_collection = mongo.db.issues

# --- JWT Custom Claims for Role-Based Access ---
@jwt.additional_claims_loader
def add_claims_to_access_token(identity):
    user = users_collection.find_one({"username": identity}, {"role": 1})
    if user:
        return {"role": user.get("role")}
    return {"role": "guest"} # Default role if user not found (shouldn't happen with valid token)

# --- JWT Error Handlers ---
@jwt.unauthorized_loader
def unauthorized_response(callback):
    return jsonify({"message": "Missing or invalid token. Please log in."}), 401

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return jsonify({"message": "Signature verification failed. Invalid token."}), 403

@jwt.expired_token_loader
def expired_token_response(callback):
    return jsonify({"message": "Token has expired. Please log in again."}), 401

# --- Helper for Role-Based Access Control ---
def role_required(allowed_roles):
    def decorator(fn):
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get("role")
            if user_role not in allowed_roles:
                return jsonify({"message": "Access forbidden: Insufficient permissions."}), 403
            return fn(*args, **kwargs)
        # Flask needs a unique endpoint name when decorators wrap functions
        # This ensures that 'wrapper' from one role_required doesn't conflict with another
        wrapper.__name__ = fn.__name__ # Set wrapper's name to original function name for Flask
        return wrapper
    return decorator


# --- API Endpoints ---

# Auth: Register User
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "resident") # Default to resident
    address = data.get("address", "") # Address optional for non-residents

    if not username or not password:
        return jsonify({"message": "Username and password are required."}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"message": "Username already exists."}), 409

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Admins require manual approval by the 'admin' (master admin) user
    status = "approved"
    if role == "admin" and username != "admin": # 'admin' user is auto-approved
        status = "pending"
        
    new_user = {
        "username": username,
        "password": hashed_password,
        "role": role,
        "address": address,
        "status": status # For admin approval workflow
    }
    users_collection.insert_one(new_user)

    if status == "pending":
        return jsonify({"message": f"User {username} registered as {role}. Awaiting admin approval."}), 201
    else:
        return jsonify({"message": f"User {username} registered successfully as {role}."}), 201

# Auth: Login User
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username and password are required."}), 400

    user = users_collection.find_one({"username": username})

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"message": "Invalid credentials."}), 401
    
    # Check admin approval status
    if user.get("status") == "pending":
        return jsonify({"message": "Your account is pending admin approval."}), 403
    elif user.get("status") == "rejected":
        return jsonify({"message": "Your account has been rejected by an admin."}), 403

    access_token = create_access_token(identity=username)
    return jsonify(
        access_token=access_token,
        user={
            "username": user["username"],
            "role": user["role"],
            "address": user.get("address", "")
        }
    ), 200

# User: Get or Update Profile
@app.route("/api/users/profile", methods=["GET", "PUT"])
@jwt_required()
def profile():
    current_user_identity = get_jwt_identity()
    user = users_collection.find_one({"username": current_user_identity})

    if not user:
        return jsonify({"message": "User not found."}), 404

    if request.method == "GET":
        return jsonify({
            "user": {
                "username": user["username"],
                "role": user["role"],
                "address": user.get("address", "")
            }
        }), 200
    elif request.method == "PUT":
        data = request.get_json()
        new_address = data.get("address") # Only allow address update for simplicity

        update_fields = {}
        if new_address is not None:
            update_fields["address"] = new_address

        if update_fields:
            users_collection.update_one({"username": current_user_identity}, {"$set": update_fields})
            updated_user = users_collection.find_one({"username": current_user_identity})
            return jsonify({
                "message": "Profile updated successfully.",
                "user": {
                    "username": updated_user["username"],
                    "role": updated_user["role"],
                    "address": updated_user.get("address", "")
                }
            }), 200
        return jsonify({"message": "No fields to update."}), 400

# Issues: Get All Issues (filtered by role)
@app.route("/api/issues", methods=["GET"], endpoint="get_issues_endpoint") # Added endpoint
@jwt_required() # This is needed even without role_required due to the wrapper
def get_issues():
    claims = get_jwt()
    current_user_role = claims.get("role")
    current_user_username = get_jwt_identity()

    if current_user_role in ["admin", "service"]:
        # Admins and Service Team can see all issues, sorted by most recent
        issues = list(issues_collection.find({}).sort("date", -1))
    elif current_user_role == "resident":
        # Residents only see their own reported issues, sorted by most recent
        issues = list(issues_collection.find({"reporter": current_user_username}).sort("date", -1))
    else:
        return jsonify({"message": "Access forbidden: Insufficient permissions."}), 403

    # Convert ObjectId to string for JSON serialization and datetime to string
    for issue in issues:
        issue["_id"] = str(issue["_id"])
        issue["date"] = issue["date"].isoformat()
        if "comments" in issue:
            for comment in issue["comments"]:
                comment["date"] = comment["date"].isoformat()

    return jsonify(issues), 200

# Issues: Create New Issue
@app.route("/api/issues", methods=["POST"], endpoint="create_issue_endpoint") # Added endpoint
@role_required(["resident"]) # Only residents can create issues
def create_issue():
    data = request.get_json()
    current_user_username = get_jwt_identity()

    required_fields = ["title", "description", "type", "location"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"message": f"{field.capitalize()} is required."}), 400

    new_issue = {
        "title": data["title"],
        "description": data["description"],
        "type": data["type"],
        "location": data["location"],
        "reporter": current_user_username,
        "date": datetime.now(),
        "status": "New", # Default status
        "assignedTo": None, # Use None for unassigned
        "comments": [],
        "photoUrl": data.get("photoUrl", "") # Placeholder for photo URL (base64 string for demo)
    }
    result = issues_collection.insert_one(new_issue)
    
    # Return the newly created issue with its ID and correct date format
    new_issue["_id"] = str(result.inserted_id)
    new_issue["date"] = new_issue["date"].isoformat()
    return jsonify(new_issue), 201

# Issues: Update Issue (Admin/Service Team)
@app.route("/api/issues/<id>", methods=["PUT"], endpoint="update_issue_endpoint") # Added endpoint
@role_required(["admin", "service"]) # Only admin/service can update issues
def update_issue(id):
    data = request.get_json()
    current_user_username = get_jwt_identity()

    try:
        object_id = ObjectId(id) # Convert string ID to ObjectId
    except Exception:
        return jsonify({"message": "Invalid Issue ID format."}), 400

    issue = issues_collection.find_one({"_id": object_id})
    if not issue:
        return jsonify({"message": "Issue not found."}), 404

    update_fields = {}
    if "assignedTo" in data:
        update_fields["assignedTo"] = data["assignedTo"] if data["assignedTo"] else None # Allow setting to null/None
    if "status" in data:
        update_fields["status"] = data["status"]
    
    if update_fields:
        issues_collection.update_one({"_id": object_id}, {"$set": update_fields})

    if "comment" in data and data["comment"]: # Add new comment if provided
        new_comment = {
            "author": current_user_username,
            "text": data["comment"],
            "date": datetime.now()
        }
        issues_collection.update_one({"_id": object_id}, {"$push": {"comments": new_comment}})

    # Fetch updated issue to return it with current data
    updated_issue = issues_collection.find_one({"_id": object_id})
    updated_issue["_id"] = str(updated_issue["_id"]) # Convert ObjectId to string
    updated_issue["date"] = updated_issue["date"].isoformat() # Convert datetime to string
    if "comments" in updated_issue:
        for comment in updated_issue["comments"]:
            comment["date"] = comment["date"].isoformat() # Convert datetime to string

    return jsonify(updated_issue), 200

# Admin Management: Get All Admin Accounts (Master Admin Only)
@app.route("/api/admins", methods=["GET"], endpoint="get_admin_accounts_endpoint") # Added endpoint
@jwt_required()
def get_admin_accounts():
    claims = get_jwt()
    current_user_username = get_jwt_identity()
    current_user_role = claims.get("role")

    if current_user_username != "admin" or current_user_role != "admin":
        return jsonify({"message": "Access forbidden: Only the master admin can view this page."}), 403

    # Fetch all users who have the 'admin' role, excluding the master admin itself
    admin_users = list(users_collection.find({"role": "admin", "username": {"$ne": "admin"}}, {"password": 0})) # Exclude password field
    for admin_user in admin_users:
        admin_user["_id"] = str(admin_user["_id"]) # Convert ObjectId to string
    return jsonify(admin_users), 200

# Admin Management: Approve or Reject Admin Accounts (Master Admin Only)
@app.route("/api/admins/<username>/<action>", methods=["PUT"], endpoint="manage_admin_status_endpoint") # Added endpoint
@jwt_required()
def manage_admin_status(username, action):
    claims = get_jwt()
    current_user_username = get_jwt_identity()
    current_user_role = claims.get("role")

    if current_user_username != "admin" or current_user_role != "admin":
        return jsonify({"message": "Access forbidden: Only the master admin can perform this action."}), 403
    
    if action not in ["approve", "reject"]:
        return jsonify({"message": "Invalid action. Must be 'approve' or 'reject'."}), 400

    user_to_update = users_collection.find_one({"username": username, "role": "admin"})

    if not user_to_update:
        return jsonify({"message": "Admin user not found or not an admin role."}), 404

    if username == "admin": # Prevent master admin from approving/rejecting itself
        return jsonify({"message": "Cannot modify the master admin account."}), 403

    new_status = "approved" if action == "approve" else "rejected"
    
    users_collection.update_one({"username": username}, {"$set": {"status": new_status}})
    
    return jsonify({"message": f"Admin user {username} status updated to {new_status}."}), 200


if __name__ == "__main__":
    # Create a default 'admin' user if it doesn't exist on first run
    # This happens when `app.py` is run directly
    with app.app_context(): # Ensure app context for MongoDB operations outside requests
        if not users_collection.find_one({"username": "admin"}):
            print("Creating default 'admin' user...")
            users_collection.insert_one({
                "username": "admin",
                "password": generate_password_hash("admin123", method='pbkdf2:sha256'), # DEFAULT PASSWORD: admin123
                "role": "admin",
                "address": "Community Office",
                "status": "approved"
            })
            print("Default admin user created. Username: admin, Password: admin123")
        
        # Also create a default resident and service user for testing convenience
        if not users_collection.find_one({"username": "resident"}):
            users_collection.insert_one({
                "username": "resident",
                "password": generate_password_hash("pass", method='pbkdf2:sha256'),
                "role": "resident",
                "address": "123 Main St, Apt 101",
                "status": "approved"
            })
            print("Default resident user created. Username: resident, Password: pass")
        
        if not users_collection.find_one({"username": "service"}):
            users_collection.insert_one({
                "username": "service",
                "password": generate_password_hash("pass", method='pbkdf2:sha256'),
                "role": "service",
                "address": "Tech Team Base",
                "status": "approved"
            })
            print("Default service user created. Username: service, Password: pass")

    app.run(debug=True, port=5000) # Run Flask app on port 5000
