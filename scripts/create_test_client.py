#!/usr/bin/env python3
"""
Script to create a test client account directly (bypassing OTP verification).
This is useful for development and testing purposes.

Usage:
    python scripts/create_test_client.py
    python scripts/create_test_client.py --email test@example.com --password TestPass123!
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
import argparse
from app.services.user import UserService
from app.models.user import UserCreate
from app.core.db import database

def create_test_client(
    email: str = "testclient@example.com",
    password: str = "TestClient123!",
    first_name: str = "Test",
    last_name: str = "Client",
    phone_number: str = "+1234567890",
    force: bool = False
):
    """
    Create a test client account directly.
    
    Args:
        email: Email address for the test account
        password: Password (must meet requirements: 8+ chars, uppercase, lowercase, number, special char)
        first_name: First name
        last_name: Last name
        phone_number: Phone number
    """
    print(f"Creating test client account...")
    print(f"Email: {email}")
    print(f"Name: {first_name} {last_name}")
    
    # Initialize user service
    user_service = UserService()
    
    # Check if user already exists
    existing_user = database["user"].find_one({"email": email})
    if existing_user:
        if not force:
            print(f"\n⚠️  User with email {email} already exists!")
            print(f"   User ID: {existing_user.get('user_id')}")
            print(f"   Role: {existing_user.get('role')}")
            print(f"   Status: {existing_user.get('status')}")
            print(f"   Name: {existing_user.get('first_name')} {existing_user.get('last_name')}")
            print(f"\n💡 You can:")
            print(f"   1. Use this existing account to login")
            print(f"   2. Run the script with a different email: --email newemail@example.com")
            print(f"\n📝 To login, use:")
            print(f"   Email: {email}")
            print(f"   Password: (the password you set when creating this account)")
            return existing_user
        else:
            print(f"⚠️  User exists but --force flag is set. Attempting to create anyway...")
            print(f"   Note: This will likely fail if user exists in Keycloak")
    
    # Create user data
    # Note: We set email_verified=True to bypass OTP check
    # The service will still create the user in Keycloak and MongoDB
    user_data = UserCreate(
        user_id=str(uuid.uuid4()),
        email=email,
        passcode=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role="CL",  # Client role
        status="ACTIVE",
        email_verified=True,  # Bypass OTP verification for test accounts
        username=f"{first_name.lower()}{last_name.lower()}",
    )
    
    try:
        # Create user (this will create in both Keycloak and MongoDB)
        created_user = user_service.create_user(user_data)
        
        print(f"\n✅ Test client account created successfully!")
        print(f"   User ID: {created_user.get('user_id')}")
        print(f"   Email: {created_user.get('email')}")
        print(f"   Role: {created_user.get('role')}")
        print(f"   Status: {created_user.get('status')}")
        print(f"\n📝 Login credentials:")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        
        return created_user
        
    except Exception as e:
        print(f"\n❌ Error creating test client account: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description="Create a test client account")
    parser.add_argument(
        "--email",
        type=str,
        default="testclient@example.com",
        help="Email address for the test account (default: testclient@example.com)"
    )
    parser.add_argument(
        "--password",
        type=str,
        default="TestClient123!",
        help="Password for the test account (default: TestClient123!)"
    )
    parser.add_argument(
        "--first-name",
        type=str,
        default="Test",
        help="First name (default: Test)"
    )
    parser.add_argument(
        "--last-name",
        type=str,
        default="Client",
        help="Last name (default: Client)"
    )
    parser.add_argument(
        "--phone",
        type=str,
        default="+1234567890",
        help="Phone number (default: +1234567890)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force creation even if email exists (WARNING: This will fail if user exists in Keycloak)"
    )
    
    args = parser.parse_args()
    
    # Validate password meets requirements
    import re
    password_pattern = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\",.<>\/?\\|`~])"
    if len(args.password) < 8:
        print("❌ Error: Password must be at least 8 characters long")
        sys.exit(1)
    if not re.search(password_pattern, args.password):
        print("❌ Error: Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character")
        sys.exit(1)
    
    create_test_client(
        email=args.email,
        password=args.password,
        first_name=args.first_name,
        last_name=args.last_name,
        phone_number=args.phone,
        force=args.force
    )


if __name__ == "__main__":
    main()

