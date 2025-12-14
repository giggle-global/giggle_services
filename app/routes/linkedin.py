import hashlib
import json
import logging
import os
import time
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import config
from app.core.keycloak import get_current_user
from app.services.user import UserService
from app.schemas.response import ok, APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn Verification"])


class LinkedInCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


def get_user_service() -> UserService:
    return UserService()


def _sanitize_scopes(raw_scopes: str) -> str:
    """
    Accepts a raw scope string, filters to allowed values, and returns a space-joined scope string.
    Uses OpenID Connect scopes (openid, profile, email) and REST API scope (r_profile_basicinfo) for profile URL.
    """
    allowed = {"openid", "profile", "email", "r_profile_basicinfo"}
    tokens = (raw_scopes or "").replace(",", " ").split()
    filtered = [t for t in tokens if t in allowed]
    if not filtered:
        filtered = ["openid", "profile", "email", "r_profile_basicinfo"]
    # Ensure openid is always included for OpenID Connect
    if "openid" not in filtered:
        filtered.insert(0, "openid")
    # Add r_profile_basicinfo if not present (for profile URL access)
    if "r_profile_basicinfo" not in filtered:
        filtered.append("r_profile_basicinfo")
    return " ".join(filtered)


def _get_linkedin_config():
    client_id = config.get("linkedin_client_id")
    client_secret = config.get("linkedin_client_secret")
    redirect_uri = config.get("linkedin_redirect_uri")
    scopes = _sanitize_scopes(config.get("linkedin_scopes", "openid profile email"))

    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LinkedIn OAuth is not configured. Please set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, and LINKEDIN_REDIRECT_URI.",
        )
    return client_id, client_secret, redirect_uri, scopes


@router.get("/auth-url", response_model=APIResponse[dict])
def get_auth_url():
    from urllib.parse import quote
    client_id, _, redirect_uri, scopes = _get_linkedin_config()
    scope_param = "%20".join(scopes.split())
    state = str(int(time.time()))
    # URL encode the redirect_uri
    encoded_redirect_uri = quote(redirect_uri, safe='')
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={client_id}"
        f"&redirect_uri={encoded_redirect_uri}"
        f"&scope={scope_param}"
        f"&state={state}"
    )
    logger.info(f"Generated auth URL with redirect_uri: {redirect_uri}")
    return ok(data={"auth_url": auth_url}, message="LinkedIn auth URL generated")


def _exchange_code_for_token(code: str, redirect_uri: str, client_id: str, client_secret: str) -> str:
    # Use OpenID Connect token endpoint
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    logger.info(f"Exchanging code for token: redirect_uri={redirect_uri}, client_id={client_id[:10]}...")
    resp = requests.post(token_url, data=payload, timeout=10)
    
    if resp.status_code != 200:
        error_text = resp.text
        try:
            error_json = resp.json()
            error_detail = error_json.get("error_description") or error_json.get("error") or error_text
        except:
            error_detail = error_text
        
        logger.error("LinkedIn token exchange failed: %s - %s", resp.status_code, error_detail)
        logger.error("Request details: redirect_uri=%s, code_length=%d", redirect_uri, len(code) if code else 0)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 
            f"Failed to exchange code with LinkedIn: {error_detail}"
        )
    
    try:
        token_data = resp.json()
    except Exception as e:
        logger.error("Failed to parse token response: %s", str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid response from LinkedIn")
    
    token = token_data.get("access_token")
    if not token:
        logger.error("No access_token in response: %s", token_data)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No access token returned by LinkedIn")
    
    logger.info("Token exchange successful, token length: %d", len(token))
    return token


def _fetch_profile(token: str) -> dict:
    """
    Fetch LinkedIn profile. Try multiple endpoints to get profile URL.
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    # Make requests in parallel immediately (before token gets revoked)
    import concurrent.futures
    
    logger.info("Making parallel requests to get LinkedIn profile data")
    
    def fetch_userinfo():
        """OpenID Connect endpoint - always works"""
        try:
            resp = requests.get(
                "https://api.linkedin.com/v2/userinfo",
                headers=headers,
                timeout=3,
            )
            return resp if resp.status_code == 200 else None
        except Exception as e:
            logger.warning(f"Error fetching /v2/userinfo: {str(e)}")
            return None
    
    def fetch_identity_me():
        """REST API endpoint - returns profileUrl with r_profile_basicinfo scope"""
        try:
            headers_with_version = {
                **headers,
                "LinkedIn-Version": "202410"  # Use stable version (202410 is widely supported)
            }
            resp = requests.get(
                "https://api.linkedin.com/rest/identityMe",
                headers=headers_with_version,
                timeout=5,
            )
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 403:
                logger.warning(f"LinkedIn /rest/identityMe returned 403 - r_profile_basicinfo scope not approved. Upgrade to Lite tier for profile URL access.")
                return None
            elif resp.status_code == 401:
                logger.warning(f"LinkedIn /rest/identityMe returned 401 - Token invalid or expired.")
                return None
            else:
                logger.warning(f"LinkedIn /rest/identityMe returned {resp.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching LinkedIn /rest/identityMe")
            return None
        except Exception as e:
            logger.error(f"Error fetching LinkedIn /rest/identityMe: {str(e)}")
            return None
    
    def fetch_me():
        """Legacy v2 API - may return vanityName"""
        try:
            projections = [
                "(id,vanityName)",
                "(id,vanityName,localizedFirstName,localizedLastName)",
                "(id)",
            ]
            for projection in projections:
                try:
                    resp = requests.get(
                        f"https://api.linkedin.com/v2/me?projection={projection}",
                        headers=headers,
                        timeout=3,
                    )
                    if resp.status_code == 200:
                        return resp
                    elif resp.status_code == 403:
                        logger.warning(f"/v2/me with projection '{projection}' returned 403 - permission denied")
                    else:
                        logger.warning(f"/v2/me with projection '{projection}' returned {resp.status_code}")
                except Exception as e:
                    logger.warning(f"Error trying projection '{projection}': {str(e)}")
                    continue
            return None
        except Exception as e:
            logger.error(f"Error in fetch_me: {str(e)}")
            return None
    
    # Execute all requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_userinfo = executor.submit(fetch_userinfo)
        future_identity_me = executor.submit(fetch_identity_me)
        future_me = executor.submit(fetch_me)
        
        userinfo_resp = future_userinfo.result()
        identity_me_resp = future_identity_me.result()
        me_resp = future_me.result()
    
    # Combine results
    profile_data = {}
    
    # Start with OpenID Connect data (always available)
    if userinfo_resp:
        userinfo_data = userinfo_resp.json()
        profile_data.update(userinfo_data)
    
    # Try REST API /identityMe for profileUrl (requires r_profile_basicinfo scope + Lite tier)
    if identity_me_resp:
        try:
            identity_data = identity_me_resp.json()
            
            # Extract profileUrl - check multiple possible structures
            profile_url = None
            
            # Structure 1: basicInfo.profileUrl (most common)
            if 'basicInfo' in identity_data:
                basic_info = identity_data['basicInfo']
                if isinstance(basic_info, dict) and 'profileUrl' in basic_info:
                    profile_url = basic_info['profileUrl']
            
            # Structure 2: Direct profileUrl (fallback)
            if not profile_url and 'profileUrl' in identity_data:
                profile_url = identity_data['profileUrl']
            
            # Structure 3: Check other nested structures
            if not profile_url:
                for key, value in identity_data.items():
                    if isinstance(value, dict) and 'profileUrl' in value:
                        profile_url = value['profileUrl']
                        break
            
            if profile_url:
                profile_data['profileUrl'] = profile_url
                logger.info(f"LinkedIn profile URL retrieved: {profile_url}")
                
                # Extract vanityName from URL
                if 'linkedin.com/in/' in profile_url.lower():
                    vanity = profile_url.lower().split('linkedin.com/in/')[-1].split('/')[0].split('?')[0]
                    if vanity:
                        profile_data['vanityName'] = vanity
            else:
                logger.warning(f"LinkedIn /rest/identityMe response received but no profileUrl found. Upgrade to Lite tier for profile URL access.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LinkedIn /rest/identityMe response: {str(e)}")
        except Exception as e:
            logger.warning(f"Error parsing LinkedIn /rest/identityMe response: {str(e)}")
    
    # Try legacy v2/me for vanityName (fallback)
    if me_resp and not profile_data.get('vanityName'):
        try:
            me_data = me_resp.json()
            if me_data.get('vanityName'):
                profile_data['vanityName'] = me_data.get('vanityName')
        except Exception as e:
            logger.warning(f"Error parsing LinkedIn /v2/me response: {str(e)}")
    
    if not profile_data:
        error_msg = "Could not fetch LinkedIn profile. The access token was revoked or expired."
        logger.error(error_msg)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error_msg)
    
    return profile_data


def _extract_vanity_from_url(url: Optional[str]) -> Optional[str]:
    """Extract vanity name from LinkedIn URL"""
    if not url:
        return None
    lowered = url.strip().lower()
    if "linkedin.com/in/" not in lowered:
        return None
    parts = lowered.split("linkedin.com/in/", 1)[1]
    vanity = parts.split("/")[0].split("?")[0]  # Remove query params
    return vanity or None


def _validate_linkedin_url(url: str) -> tuple:
    """
    Validate LinkedIn profile URL format.
    Returns (is_valid, normalized_url)
    """
    if not url or not isinstance(url, str):
        return False, None
    
    url = url.strip()
    
    # Normalize URL - add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # Check if it's a valid LinkedIn profile URL
    patterns = [
        r'^https?://(www\.)?linkedin\.com/in/[^/\s?]+',
        r'^https?://linkedin\.com/in/[^/\s?]+',
    ]
    
    import re
    for pattern in patterns:
        if re.match(pattern, url, re.IGNORECASE):
            # Normalize to https://www.linkedin.com/in/username format
            normalized = re.sub(r'^https?://(www\.)?linkedin\.com/in/', 'https://www.linkedin.com/in/', url, flags=re.IGNORECASE)
            # Remove query params and trailing slashes
            normalized = normalized.split('?')[0].rstrip('/')
            return True, normalized
    
    return False, None


# Store processed codes to prevent duplicate processing (in-memory cache, expires after 5 minutes)
_processed_codes: dict[str, float] = {}
import time as time_module

@router.post("/callback", response_model=APIResponse[dict])
def linkedin_callback(
    request: LinkedInCallbackRequest,
    user_svc: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    global _processed_codes  # Declare global at the top
    
    code = request.code
    state = request.state
    user_id = current_user.get("user_id")
    
    # Prevent duplicate processing of the same code
    current_time = time_module.time()
    if code in _processed_codes:
        processed_time = _processed_codes[code]
        if current_time - processed_time < 300:  # 5 minutes
            logger.warning(f"Duplicate LinkedIn callback detected (already processed), returning cached result")
            # Return success if already processed (first call succeeded)
            return ok(message="LinkedIn verified (already processed)", data={"verified": True})
        else:
            # Code expired from cache, allow reprocessing
            del _processed_codes[code]
    
    logger.info(f"LinkedIn callback received for user {user_id}")
    
    # Mark code as being processed
    _processed_codes[code] = current_time
    
    try:
        client_id, client_secret, redirect_uri, _ = _get_linkedin_config()
        access_token = _exchange_code_for_token(code, redirect_uri, client_id, client_secret)
        
        # Fetch profile IMMEDIATELY after getting token (before it gets revoked)
        profile = _fetch_profile(access_token)
    except HTTPException as e:
        logger.error(f"LinkedIn OAuth error for user {user_id}: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during LinkedIn OAuth for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"LinkedIn verification failed: {str(e)}")

    # Extract profile information
    profile_id = profile.get("sub") or profile.get("id")
    profile_url = profile.get("profileUrl")  # From REST API
    vanity = profile.get("vanityName") or profile.get("preferred_username")
    
    if not profile_id:
        logger.error(f"No profile ID found in LinkedIn response for user {user_id}")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve LinkedIn profile ID. Please try again.",
        )

    # Determine LinkedIn URL - prefer profileUrl from REST API, then build from vanityName
    linkedin_url = None
    if profile_url:
        linkedin_url = profile_url
        # Extract vanity from URL if not already present
        if not vanity and 'linkedin.com/in/' in profile_url:
            vanity = profile_url.split('linkedin.com/in/')[-1].split('/')[0].split('?')[0]
        logger.info(f"LinkedIn verification successful for user {user_id}: URL={linkedin_url}")
    elif vanity:
        linkedin_url = f"https://www.linkedin.com/in/{vanity}"
        logger.info(f"LinkedIn verification successful for user {user_id}: URL={linkedin_url}")
    else:
        logger.info(f"LinkedIn verification successful for user {user_id} (no URL returned - upgrade to Lite tier for automatic URL)")

    # Get existing user data
    user = user_svc.user_repo.get_user_by_id(current_user.get("user_id"))

    # Merge LinkedIn verification fields with existing contact_info to preserve other fields
    existing_contact_info = user.get("contact_info") or {}
    updated_contact_info = {
        **existing_contact_info,  # Preserve all existing fields
        "linkedin_verified": True,
        "linkedin_profile_id": profile_id,
        "linkedin_verified_at": int(time.time()),
    }
    
    # Only set URL and vanity if we have them
    if linkedin_url and vanity:
        updated_contact_info["linkedin"] = linkedin_url
        updated_contact_info["linkedin_vanity"] = vanity
    # If no URL, keep existing URL if it exists, otherwise leave empty
    elif existing_contact_info.get("linkedin"):
        logger.info(f"Keeping existing LinkedIn URL: {existing_contact_info.get('linkedin')}")
    
    updated_user = user_svc.user_repo.update_user(
        user_id=current_user.get("user_id"),
        update_payload={
            "contact_info": updated_contact_info,
        },
    )
    
    if not updated_user:
        logger.error(f"Failed to update LinkedIn verification for user {current_user.get('user_id')}")

    # Clean up old codes from cache (older than 5 minutes)
    cutoff_time = current_time - 300
    _processed_codes = {k: v for k, v in _processed_codes.items() if v > cutoff_time}

    return ok(message="LinkedIn verified", data={"verified": True, "linkedin_url": linkedin_url})


class LinkedInUrlUpdateRequest(BaseModel):
    linkedin_url: str


@router.post("/update-url", response_model=APIResponse[dict])
def update_linkedin_url(
    request: LinkedInUrlUpdateRequest,
    user_svc: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Manually update LinkedIn URL. Validates URL format and updates user profile.
    """
    user_id = current_user.get("user_id")
    linkedin_url = request.linkedin_url
    
    logger.info(f"Manual LinkedIn URL update requested for user {user_id}: {linkedin_url}")
    
    # Validate URL format
    is_valid, normalized_url = _validate_linkedin_url(linkedin_url)
    if not is_valid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid LinkedIn URL format. Please use format: https://www.linkedin.com/in/username"
        )
    
    # Get existing user data
    user = user_svc.user_repo.get_user_by_id(user_id)
    existing_contact_info = user.get("contact_info") or {}
    
    # Extract vanity name from URL
    vanity = _extract_vanity_from_url(normalized_url)
    
    # Update contact_info - preserve verification status if already verified
    updated_contact_info = {
        **existing_contact_info,
        "linkedin": normalized_url,
        "linkedin_vanity": vanity,
    }
    
    # If not already verified, don't set verified status (user needs to verify via OAuth)
    # If already verified, keep the verification status
    
    logger.info(f"Updating LinkedIn URL for user {user_id}: {normalized_url}")
    
    updated_user = user_svc.user_repo.update_user(
        user_id=user_id,
        update_payload={
            "contact_info": updated_contact_info,
        },
    )
    
    if updated_user:
        logger.info(f"LinkedIn URL updated successfully for user {user_id}")
        return ok(
            message="LinkedIn URL updated successfully",
            data={"linkedin_url": normalized_url, "verified": existing_contact_info.get("linkedin_verified", False)}
        )
    else:
        logger.error(f"Failed to update LinkedIn URL for user {user_id}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update LinkedIn URL"
        )

