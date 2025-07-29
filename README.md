# Community-Complaint-Portal
Developed a full-stack web portal to streamline community issue reporting and resolution. Implemented secure role-based access for Residents, Admins, Service Teams, and Master Admins. The system allows users to report issues with images, track resolution progress, assign technicians, and view analytics. Key features include token-based authentication, real-time issue tracking, comment logs, and admin approval workflows. Deployed the application using Render (backend), Netlify (frontend), and MongoDB Atlas (cloud database).
Highlights:
Designed REST APIs with Flask and JWT-based session management.
Developed responsive UI with modular dashboards for different user roles.
Built a scalable NoSQL schema to manage issue lifecycle and user roles.
Integrated live analytics, status filters, and admin control panels.
Achieved full deployment on cloud platforms with seamless frontend-backend communication.

Step 1: Clone the Repository
bash
Copy
Edit
git clone https://github.com/your-username/community-issue-portal.git
cd community-issue-portal/backend
Step 2: Create and Activate Virtual Environment
bash
Copy
Edit
python -m venv venv
source venv/bin/activate     # On Windows: venv\Scripts\activate
Step 3: Install Dependencies
bash
Copy
Edit
pip install -r requirements.txt
Step 4: Create .env File
Inside the backend/ folder, create a .env file with the following content:

env
Copy
Edit
MONGO_URI = "mongodb+srv://your_mongodb_user:your_mongodb_password@cluster0.mongodb.net/issue-portal?retryWrites=true&w=majority"
JWT_SECRET_KEY = "supersecretkey123"
✅ Note: Replace with your actual MongoDB connection URI.

Step 5: Run the Flask App
bash
Copy
Edit
python app.py
The server will start on:

arduino
Copy
Edit
http://localhost:5000
🌐 Frontend Setup (Static HTML + JS + Tailwind CSS)
Step 1: Navigate to Frontend Directory
bash
Copy
Edit
cd ../frontend
Step 2: Serve Files
You can open index.html directly in a browser or use a simple HTTP server:

bash
Copy
Edit
# Using Python 3
python -m http.server 8080
Now open:

arduino
Copy
Edit
http://localhost:8080
Make sure the frontend JavaScript is pointing to:

javascript
Copy
Edit
const API_BASE_URL = "http://localhost:5000";

Deployed Link - https://community-complaint-portal.vercel.app/
🔑 Default Login Credentials
For demo/testing, you can manually insert or use these default test accounts:

Role	Username (email)	Password
Resident	resident@test.com	resident123
Service Team	team@test.com	team123
Admin	admin@test.com	admin123
Master Admin	masteradmin@test.com	master123
