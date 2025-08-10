# users.py
import streamlit as st
import bcrypt
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

# ======================================================================================
# MongoDB Configuration
# ======================================================================================

@st.cache_resource
def get_mongo_client():
    try:
        # Connect to MongoDB using the connection string from Streamlit's secrets
        client = MongoClient(st.secrets["MONGO_CONNECTION_STRING"])
        client.admin.command('ping') # Check if connection is successful
        return client
    except ConnectionFailure:
        st.error("Failed to connect to MongoDB. Please check your connection string in `.streamlit/secrets.toml` and ensure MongoDB is running.")
        st.stop()

# ======================================================================================
# Password Hashing Functions
# ======================================================================================

def hash_password(password):
    """Hashes a password using bcrypt."""
    # bcrypt generates a salt and hashes the password in one step
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_password(password, hashed_password):
    """Verifies a password against a hashed password."""
    # bcrypt handles the salt extraction automatically
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# ======================================================================================
# User Database Operations
# ======================================================================================

def register_user(username, password):
    """Registers a new user in the database."""
    client = get_mongo_client()
    db = client["food_agent_db"]
    users_collection = db["users"]
    
    # Hash the password before saving
    hashed_password = hash_password(password)
    
    try:
        users_collection.insert_one({"username": username, "password": hashed_password})
        return True
    except DuplicateKeyError:
        return False # User already exists

def login_user(username, password):
    """Authenticates a user against the database."""
    client = get_mongo_client()
    db = client["food_agent_db"]
    users_collection = db["users"]
    
    user_data = users_collection.find_one({"username": username})
    
    if user_data:
        if verify_password(password, user_data["password"]):
            return True
    return False

# ======================================================================================
# UI for Login and Registration
# ======================================================================================

def check_login():
    """Checks if the user is authenticated via session state."""
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
        st.session_state.current_user = None
    return st.session_state.is_authenticated

def create_user_page():
    """Creates the login and registration UI in a two-column layout."""
    st.title("Welcome to My AI Food Agent")
    st.markdown("Please log in or register to get started.")

    col1, col2 = st.columns(2)

    with col1:
        st.header("Login")
        with st.form("login_form"):
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if login_user(login_username, login_password):
                    st.session_state.is_authenticated = True
                    st.session_state.current_user = login_username
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with col2:
        st.header("Register")
        with st.form("register_form"):
            register_username = st.text_input("New Username", key="register_username")
            register_password = st.text_input("New Password", type="password", key="register_password")
            register_submitted = st.form_submit_button("Register")

            if register_submitted:
                if register_user(register_username, register_password):
                    st.success("Registration successful! You can now log in.")
                else:
                    st.error("Username already exists. Please choose a different one.")
