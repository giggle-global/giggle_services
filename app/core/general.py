"""
CRUD Operation for general useage
"""

import inspect
import os
import re
import string
import random
import pytz
import time

from pymongo.collection import Collection
from datetime import datetime
from pymongo.errors import PyMongoError
from fastapi import HTTPException, Request
from app.core.response import error_response_model
from app.core.db import database
from app.core.audit_log import define_logger
from app.core.constant import error_messages
from app.core.models.audit_log import OperationType, AuditLogInfoType
from pymongo.collection import Collection
from cryptography.fernet import Fernet
from app.core.config import config

KEY = config["client_secret"].encode("utf-8")


def generate_id(length: int) -> str:
    """
    Generate a random ID consisting of uppercase letters and digits for primary key.
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    characters = string.digits + string.ascii_uppercase
    return "".join(random.choices(characters, k=length))


def generate_pk_id(length: int, prefix: str) -> str:
    """
    Generate a unique primary key ID for a document in a collection.

    Args:
        length (int): The length of the generated ID.
        prefix (str): The prefix to prepend to the generated ID.

    Returns:
        str: The unique primary key ID for the document.

    """

    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    if not isinstance(prefix, str):
        raise ValueError("Prefix must be a string.")
    pk_id = generate_id(length=length)
    return prefix + "_" + pk_id


def local_time_to_gmt_epoch():
    """
    Converts the current local time to GMT epoch time.

    Returns:
        int: The GMT epoch time.
    """
    # Get the current local time
    current_local_time = datetime.now()

    # Convert local time to GMT (UTC)
    gmt_timezone = pytz.timezone("UTC")
    current_gmt_time = current_local_time.astimezone(gmt_timezone)

    epoch = datetime(1970, 1, 1, tzinfo=pytz.utc)
    diff = current_gmt_time - epoch
    return int(diff.total_seconds())


def validate_whitespace_or_none(value):
    """
    Validates whether a value is whitespace or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if value is None or value.isspace() or value == "":
        error_response = error_response_model(code=422, error_code=1003)
        define_logger(
            level=30,
            request=None,
            user=None,
            loggName=loggername,
            pid=pid,
            message=error_messages[1003],
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value


def validate_email(value):
    """
    Validates whether a value is an email or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if not value:
        return None
    if value and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
        error_response = error_response_model(code=422, error_code=1004)
        define_logger(
            level=30, loggName=loggername, pid=pid, message=error_messages[1004]
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value


def validate_alphabets(value):
    """
    Validates whether a value is alphabets or None."""

    loggername = inspect.stack()[0]
    pid = os.getpid()

    if value and not re.match(r"^[a-zA-Z ]+$", value):
        error_response = error_response_model(code=422, error_code=1005)
        define_logger(
            level=30, loggName=loggername, pid=pid, message=error_messages[1005]
        )
        raise HTTPException(status_code=422, detail=error_response)
    return value





def auditloginfo(uid: str, name: str, ops: OperationType, prefix: str = None):
    """
    Function to generate the audit log info.
    """
    if ops == OperationType.CREATE.value:
        if prefix:
            return {
                f"{prefix}.created_on": local_time_to_gmt_epoch(),
                f"{prefix}.created_by": name,
                f"{prefix}.created_id": uid,
            }
        return {
            "created_on": local_time_to_gmt_epoch(),
            "created_by": name,
            "created_id": uid,
        }
    if ops == OperationType.UPDATE.value:
        if prefix:
            return {
                f"{prefix}.modified_on": local_time_to_gmt_epoch(),
                f"{prefix}.modified_by": name,
                f"{prefix}.modified_id": uid,
            }
        return {
            "modified_on": local_time_to_gmt_epoch(),
            "modified_by": name,
            "modified_id": uid,
        }


def create_unique_index(
    collection_name: str,
    field: str,
    user: dict = None,
    request=None,
):
    """Create a Unique index for the given field if it's not already created"""
    loggername = inspect.stack()[0]
    pid = os.getpid()
    try:
        collection: Collection = database[collection_name]
        index_info = collection.index_information()
        if field not in index_info:
            return collection.create_index([(field, 1)], unique=True)
        return None
    except PyMongoError as exc:

        define_logger(
            level=50,
            request=request,
            user=user,
            loggName=loggername,
            pid=pid,
            message=exc,
        )


def create_compond_index(
    collection_name: str,
    field: list,
    user: dict = None,
    request=None,
):
    """Create a Unique index for the given field if it's not already created"""
    loggername = inspect.stack()[0]
    pid = os.getpid()
    try:
        collection: Collection = database[collection_name]
        index_info = collection.index_information()
        if field not in index_info:
            collection.create_index(
                [("name", 1), ("type", 1), ("parent", 1), ("store_id", 1)],
                unique=True,
            )
        return None
    except PyMongoError as exc:
        error_response = error_response_model(code=500, error_code=3000)
        define_logger(
            level=50,
            request=request,
            user=user,
            loggName=loggername,
            pid=pid,
            message=error_messages[3000],
        )
        raise HTTPException(status_code=500, detail=error_response) from exc


# Function to encrypt a string
def encrypt_string(plain_text):
    fernet = Fernet(KEY)

    # Check if plain_text is already in bytes, if not, encode it
    if isinstance(plain_text, str):
        plain_text = plain_text.encode()  # Convert to bytes if it's a string

    encrypted_password = fernet.encrypt(plain_text)
    return encrypted_password.decode()  # Return as a string


# Function to decrypt a string
def decrypt_string(encrypted_text):
    fernet = Fernet(KEY)

    # Ensure the encrypted_text is in bytes, if it's a string, encode it
    if isinstance(encrypted_text, str):
        encrypted_text = encrypted_text.encode()  # Convert to bytes if it's a string

    decrypted_text = fernet.decrypt(
        encrypted_text
    ).decode()  # Decrypt and convert back to string
    return decrypted_text


def generate_passcode() -> str:
    return str(random.randint(1000, 9999))


def initialize_audit_log(current_user, existing_audit_log=None):
    """Initialize or update the audit log based on whether it's a new or modified entity."""
    timestamp = int(datetime.utcnow().timestamp())

    # Extract user details
    first_name = current_user["firstName"]
    last_name = current_user["lastName"] if current_user.get("lastName") != " " else ""
    user_name = f"{first_name} {last_name}"
    user_id = current_user["attributes"]["user_id"][0].upper()

    # If this is an existing entity, update the modification details
    if existing_audit_log:
        # If existing_audit_log is a dict, convert it to AuditLogInfoType
        if isinstance(existing_audit_log, dict):
            existing_audit_log = AuditLogInfoType(**existing_audit_log)

        # Modify the existing audit log without changing creation details
        existing_audit_log.modified_by = user_name
        existing_audit_log.modified_id = user_id
        existing_audit_log.modified_on = timestamp

        return existing_audit_log

    else:
        # Return a new instance of AuditLogInfoType with creation details
        return AuditLogInfoType(
            created_by=user_name,
            created_id=user_id,
            created_on=timestamp,
        )


def generate_epoch_with_string(append_str):
    # Get the current epoch time in seconds
    epoch_time = int(time.time())

    # Convert epoch time to string and append the provided string
    result = f"{epoch_time}_{append_str}"

    return result

def generate_random_name() -> str:
    """Generate a unique random username with 3+4 or 4+3 letter words plus 2-3 digits.
    Pattern: word1word2 + digits (where word1 is 3 or 4 letters, word2 is 4 or 3 letters)
    Examples: airtree27, skydata91, greentek308, clearnet42, cloudway517
    
    Note: This function performs a pre-check for uniqueness, but the final guarantee
    is enforced by a unique database index on the username field. If a race condition
    occurs (two requests generate the same username simultaneously), the database
    will reject the duplicate and the user service will retry with a new username.
    """
    max_attempts = 100  # Prevent infinite loops
    user_collection = database["user"]
    
    for attempt in range(max_attempts):
        # Randomly choose 3+4 or 4+3 pattern
        if random.choice([True, False]):  # 3+4 pattern
            word1 = random.choice(three_letter_words)
            word2 = random.choice(four_letter_words)
        else:  # 4+3 pattern
            word1 = random.choice(four_letter_words)
            word2 = random.choice(three_letter_words)
        
        # Generate random digits (2-3 digits: 00-999)
        num_digits = random.choice([2, 3])
        if num_digits == 2:
            digits = f"{random.randint(0, 99):02d}"
        else:
            digits = f"{random.randint(0, 999):03d}"
        
        # Combine: word1word2 + digits (all lowercase)
        username = f"{word1}{word2}{digits}"
        
        # Pre-check if username already exists in database (optimization to avoid DB errors)
        # Final uniqueness is guaranteed by database unique index
        existing = user_collection.find_one({"username": username})
        if not existing:
            return username
    
    # If we couldn't generate a unique username after max attempts, raise an error
    raise HTTPException(
        status_code=500,
        detail="Unable to generate a unique username. Please try again."
    )


# Curated list of username-friendly 3-letter English words
# Excludes: animals, body parts, actions, negative words, abstract/grammar words
three_letter_words = [
    # Objects & Items (positive, relatable, common)
    'box', 'bag', 'cup', 'pen', 'key', 'hat', 'map', 'bed', 'rug', 'toy', 'jar', 'pan', 'pot', 'can', 'lid', 'tag', 'pin', 'fan', 'bar', 'cap', 'mug', 'web', 'gem', 'log', 'rod', 'tub', 'van', 'bow', 'arc', 'ray', 'hub', 'kit', 'lab', 'mat', 'net', 'pad', 'peg', 'saw', 'tap', 'urn', 'vat', 'wax', 'zip', 'cab', 'car', 'cod', 'cog', 'cot', 'cub', 'cue', 'den', 'dew', 'dot', 'dye', 'fan', 'far', 'fax', 'fee', 'fen', 'few', 'fig', 'fin', 'fir', 'fit', 'fix', 'fog', 'fry', 'fun', 'fur', 'gal', 'gap', 'gas', 'gel', 'gem', 'gig', 'gin', 'gum', 'guy', 'gym', 'ham', 'hat', 'hay', 'hex', 'hub', 'hue', 'hug', 'hum', 'hut', 'ice', 'icy', 'ink', 'inn', 'ion', 'ivy', 'jam', 'jar', 'jay', 'jet', 'jig', 'job', 'joy', 'jug', 'kay', 'keg', 'ken', 'key', 'kid', 'kin', 'kit', 'koa', 'koi', 'lab', 'lad', 'lag', 'lam', 'lap', 'lar', 'las', 'lat', 'law', 'lax', 'lay', 'lea', 'led', 'lee', 'lei', 'let', 'lev', 'lex', 'ley', 'lib', 'lid', 'lie', 'lin', 'lis', 'lit', 'lob', 'log', 'loo', 'lop', 'lot', 'lox', 'lug', 'lum', 'lun', 'lur', 'luv', 'lux', 'lye', 'mac', 'mag', 'man', 'map', 'mar', 'mas', 'mat', 'max', 'may', 'med', 'meg', 'mel', 'men', 'met', 'mic', 'mid', 'mil', 'min', 'mir', 'mix', 'mob', 'mod', 'mog', 'mol', 'mom', 'mon', 'moo', 'mop', 'mor', 'mos', 'mot', 'mow', 'mug', 'mum', 'nab', 'nap', 'nay', 'net', 'new', 'nil', 'nip', 'nit', 'nix', 'nob', 'nod', 'nog', 'nor', 'not', 'now', 'nub', 'nut', 'oak', 'oar', 'oat', 'odd', 'ode', 'off', 'oil', 'old', 'opt', 'orb', 'orc', 'ore', 'org', 'owe', 'owl', 'pac', 'pad', 'pal', 'pan', 'pap', 'par', 'pas', 'pat', 'paw', 'pax', 'pay', 'pea', 'pec', 'ped', 'peg', 'pen', 'pep', 'per', 'pes', 'pet', 'pew', 'pic', 'pie', 'pin', 'pip', 'pit', 'pix', 'ply', 'pod', 'poe', 'poi', 'pol', 'pom', 'pon', 'poo', 'pop', 'pot', 'pow', 'pro', 'pry', 'pub', 'pud', 'pug', 'pun', 'pup', 'pur', 'put', 'pya', 'pye', 'rad', 'rag', 'rah', 'rai', 'raj', 'ram', 'ran', 'rap', 'ras', 'raw', 'ray', 'raz', 'reb', 'rec', 'red', 'ree', 'ref', 'reg', 'rei', 'rem', 'ren', 'rep', 'res', 'ret', 'rev', 'rex', 'rez', 'rho', 'ria', 'rib', 'rid', 'rif', 'rig', 'rim', 'rin', 'rip', 'rit', 'riz', 'rob', 'roc', 'rod', 'roe', 'rog', 'rom', 'roo', 'rot', 'row', 'rub', 'ruc', 'rue', 'rug', 'rum', 'rut', 'rye', 'sab', 'sac', 'sag', 'sal', 'sam', 'san', 'sap', 'sar', 'sat', 'saw', 'sax', 'sea', 'sec', 'seg', 'sei', 'sel', 'sen', 'ser', 'sha', 'she', 'shy', 'sib', 'sic', 'sid', 'sig', 'sim', 'sin', 'sip', 'sir', 'sis', 'ski', 'sky', 'sly', 'sob', 'soc', 'sod', 'soh', 'sol', 'som', 'son', 'sop', 'sos', 'sot', 'sou', 'sov', 'sow', 'sox', 'soy', 'spa', 'spy', 'sri', 'sty', 'sub', 'sud', 'sue', 'sum', 'sun', 'sup', 'sur', 'sus', 'swy', 'tab', 'tad', 'tag', 'tam', 'tan', 'tao', 'tap', 'tar', 'tas', 'tat', 'tau', 'tav', 'taw', 'tax', 'tay', 'tea', 'tec', 'ted', 'tee', 'teg', 'tel', 'tes', 'tet', 'tew', 'tex', 'tho', 'thy', 'tic', 'tie', 'tig', 'til', 'tin', 'tip', 'tis', 'tit', 'tix', 'tod', 'toe', 'tog', 'tom', 'ton', 'too', 'top', 'tor', 'tot', 'tow', 'toy', 'tub', 'tug', 'tum', 'tun', 'tup', 'tut', 'tux', 'twa', 'tye', 'udo', 'ufo', 'uke', 'ulu', 'umm', 'ump', 'uni', 'uns', 'upo', 'ups', 'urb', 'urd', 'ure', 'urg', 'urn', 'urp', 'use', 'ush', 'usk', 'usp', 'uss', 'ute', 'uts', 'vac', 'van', 'var', 'vas', 'vat', 'vau', 'vav', 'vaw', 'vee', 'veg', 'vet', 'vex', 'via', 'vid', 'vie', 'vig', 'vim', 'vin', 'vis', 'voe', 'vog', 'vol', 'von', 'vow', 'vox', 'vug', 'vum', 'wad', 'wag', 'wan', 'wap', 'waw', 'wax', 'web', 'wed', 'wee', 'wig', 'wis', 'wit', 'wiz', 'wok', 'wop', 'wos', 'wow', 'wry', 'wud', 'wus', 'wye', 'wyn', 'yag', 'yah', 'yam', 'yap', 'yar', 'yas', 'yat', 'yaw', 'yay', 'yea', 'yeh', 'yen', 'yep', 'yes', 'yet', 'yew', 'yid', 'yin', 'yip', 'yob', 'yod', 'yok', 'yom', 'yon', 'yow', 'yox', 'yoy', 'yuk', 'yum', 'yup', 'yus', 'zag', 'zap', 'zas', 'zax', 'zed', 'zee', 'zek', 'zel', 'zen', 'zep', 'zes', 'zex', 'zez', 'zho', 'zig', 'zin', 'zip', 'zit', 'ziz', 'zoa', 'zol', 'zuz',
    
    # Nature (pleasant, relatable)
    'sun', 'sea', 'sky', 'ice', 'fog', 'dew', 'oak', 'elm', 'ash', 'fir', 'bay', 'ray', 'log',
    
    
    # Colors (positive, relatable)
    'red', 'tan',
    
    # Positive descriptive words
    'new', 'old', 'big', 'hot', 'top', 'end', 'far', 'yes', 'art', 'awe', 'fab', 'fit', 'fun', 'gem', 'joy', 'key', 'max', 'pro', 'ray', 'red', 'sky', 'sun', 'tan', 'top', 'van', 'web', 'wow', 'zen',
]

four_letter_words = [
    # # Tech-related
    # 'data', 'code', 'byte', 'node', 'link', 'flow', 'tech', 'wire', 'chip', 'disk', 'file', 'line', 'mode', 'path', 'port', 'root', 'site', 'text', 'user', 'view', 'wave', 'zone', 'base', 'core', 'edge', 'grid', 'host', 'info', 'java', 'json', 'loop', 'mail', 'meta', 'name', 'page', 'pipe', 'pool', 'push', 'rest', 'rule', 'scan', 'sign', 'size', 'sort', 'span', 'star', 'step', 'stop', 'sync', 'task', 'team', 'term', 'test', 'time', 'tool', 'type', 'unit', 'vary', 'verb', 'void',
    
    # Nature (exactly 4 letters)
    'tree', 'wind', 'wave', 'star', 'moon', 'lake', 'rock', 'sand', 'snow', 'rain', 'fire', 'bird', 'fish', 'deer', 'bear', 'wolf', 'lion', 'rose', 'leaf', 'seed', 'root', 'stem', 'bark', 'moss', 'fern', 'pine', 'clay', 'dirt', 'dust', 'mist', 'haze', 'hail',
    
    # Positive descriptive words (exactly 4 letters)
    'cool', 'warm', 'calm', 'bold', 'fast', 'slow', 'high', 'deep', 'wide', 'long', 'tall', 'tiny', 'huge', 'vast', 'full', 'rich', 'soft', 'hard', 'weak', 'kind', 'wise', 'hope', 'love', 'play', 'game', 'bond', 'fame',
    
    # Action/Verb words (exactly 4 letters)
    'flow', 'move', 'jump', 'leap', 'soar', 'sail', 'ride', 'race', 'rush', 'dash', 'roam', 'find', 'seek', 'hunt', 'lead', 'beat', 'open', 'shut', 'lock', 'make', 'work', 'play', 'rest', 'wake', 'rise', 'fall', 'drop', 'lift', 'push', 'pull', 'grab', 'toss', 'flip', 'turn', 'spin', 'bend', 'fold', 'wrap', 'bind', 'join', 'stir', 'rock', 'roll', 'slip', 'wipe', 'wash', 'soak', 'pour', 'leak', 'drip', 'snap', 'ring', 'buzz', 'roar', 'yell', 'sing', 'talk', 'chat', 'love', 'like',
]


random_names = {'vexmier', 'marsaas', 'aricour', 'beldiox', 'jasas', 'darriel', 'jasrees', 'finsais', 'zenzean', 'orataes', 
                'kaineox', 'elykiil', 'leoraes', 'corvaix', 'jasir', 'arier', 'vexcois', 'valrees', 'arifiur', 'jaser', 'jaszeox', 
                'lyloes', 'aerleum', 'valsaon', 'vexleil', 'zarloal', 'tanfiis', 'zenkaen', 'norreas', 'vexneer', 'vexvais', 'renkail', 
                'ravries', 'felmoox', 'dextael', 'zarriil', 'terer', 'neocoox', 'norzeir', 'leotail', 'neoix', 'kaikion', 'termoel', 
                'quinraur', 'darvaon', 'ravvaur', 'vexraas', 'jasreel', 'valfium', 'quinmoel', 'quinkaur', 'elyreix', 'vexsaix', 'tanmial', 
                'vexdior', 'darleor', 'vextaix', 'belsaal', 'vexzeet', 'finvaix', 'mirvael', 'neokius', 'darmium', 'elykiin', 'belsuar', 
                'zenvaox', 'jassuas', 'kaidior', 'zenmoel', 'terdiix', 'elymoal', 'zenis', 'zenfium', 'quinum', 'dexkaal', 'belmiix', 
                'norraum', 'quindiox', 'corvaan', 'elyvair', 'quinzees', 'lumrius', 'terreer', 'neocoor', 'aririil', 'elydias', 'solmien', 
                'silvael', 'zensaum', 'norzear', 'renrair', 'corfiix', 'jasis', 'cornaan', 'tertaes', 'kaileer', 'zennaar', 'lyreal', 'aermois', 
                'kaizear', 'valnees', 'zarkion', 'jasus', 'silrier', 'terkiet', 'finraox', 'leotaox', 'finsail', 'valdien', 'belleir', 'dexneel', 
                'dexkaon', 'finloel', 'valfior', 'dexmias', 'corkion', 'siler', 'elysuan', 'mirrees', 'aerkaen', 'lymous', 'feltaet', 'solkiet', 
                'arinaox', 'cortaur', 'quinzeus', 'zarsual', 'leocoix', 'belsaix', 'orazeir', 'belix', 'ravloir', 'quinkias', 'felsuet', 'sildiix', 
                'tervain', 'lumrael', 'mirvaum', 'neokaer', 'elyneen', 'neoraan', 'zenvaan', 'elymoox', 'jasfiix', 'elysuus', 'aerlous', 'zarmoet', 
                'leoneis', 'belneus', 'silkaix', 'feldias', 'vexsuet', 'elykier', 'elymoor', 'terloan', 'zensaon', 'zarmion', 'rensaon', 'markail', 'noran', 'quinfius', 'norleet', 'nortaen', 'oraloet', 'aerleon', 'zenkiir', 'solnaum', 'neodium', 'terkial', 'dexvaen', 'orakaor', 'zenreon', 'leoleus', 'rennaan', 'zarkaes', 'marfial', 'darrair', 'leosuas', 'orarais', 'terzeus', 'jasloer', 'tertain', 'nordier', 'jasreas', 'lykiix', 'zarmoar', 'tansues', 'darsail', 'ravzeon', 'quinrean', 'dexneus', 'normoir', 'terzeix', 'valzein', 'belloel', 'felreen', 'arimoin', 'arisuil', 'corfies', 'leoas', 'zencoar', 'dexmius', 'corriir', 'mirzeel', 'norsuis', 'jasmius', 'lykaal', 'valneon', 'arikior', 'belreen', 'orarein', 'oranaes', 'orareir', 'aervaes', 'terzees', 'elyzeur', 'tanreer', 'lyneor', 'vexcoen', 'norleer', 'jaskaas', 'lykaus', 'ariries', 'marmour', 'kaisuum', 'tanrais', 'renus', 'kaileel', 'oranaus', 'jasfiar', 'orarior', 'vexnaar', 'orareel', 'tansaen', 'valraes', 'finrius', 'finmoor', 'kaisuis', 'leomoox', 'lycoel', 'rensuin', 'aerfiel', 'neosuox', 'mirsues', 'oramoal', 'zenkail', 'belleil', 'elyloil', 'norvaan', 'orain', 'ravloal', 'norfial', 'felrein', 'lumas', 'elymour', 'quinkiir', 'quinkaes', 'renloox', 'zennaus', 'rentaox', 'norkiar', 'aerreis', 'quinnees', 'jassuur', 'noris', 'arikaum', 'valkium', 'norlois', 'leoleet', 'nordies', 'lumtain', 'tantael', 'solkiar', 'solneum', 'zennaal', 'oramoer', 'silzeum', 'kaireix', 'elydial', 'dexleal', 'finneix', 'valneum', 'jasloor', 'zensaix', 'vexmien', 'lumil', 'elyriox', 'oramous', 'zenzeon', 'leosaan', 'neocoum', 'jasleer', 'aervain', 'norkiix', 'tanloix', 'solloor', 'lyrail', 'lummoix', 'dexneon', 'mirdier', 'vexkial', 'norleis', 'finzeon', 'tansaum', 'belloen', 'lycoon', 'renreus', 'solkaox', 'orarien', 'quinnaer', 'tanmoel', 'lumloir', 'elymiur', 'vexreur', 'jasleal', 'rentais', 'finkaar', 'quinkiur', 'kaivaal', 'renvaon', 'arirein', 'norneen', 'jasreal', 'marreer', 'terloar', 'corvaal', 'darox', 'terraix', 'lumkaur', 'solvail', 'quinzeor', 'aerdior', 'zenneir', 'rencoix', 'vexraet', 'tersaas', 'mirloil', 'aririur', 'cornair', 'kaivain', 'quincoor', 'zarfial', 'soldias', 'tantaer', 'tantaum', 'dexfiin', 'silkael', 'quinfium', 'zaret', 'darsaor', 'termiin', 'ravrias', 'zarleox', 'tantail', 'arinaon', 'zenraet', 'aerkiin', 'dexsaen', 'markaox', 'oraneal', 'silzeix', 'aeror', 'oracoox', 'aermiur', 'jasraas', 'zarfiin', 'zensual', 'leokaus', 'vexcous', 'tersaox', 'valdiox', 'arizeen', 'tervaer', 'zarkaen', 'quindiin', 'arileox', 'quinmion', 'darsaar', 'zarvaur', 'lyloon', 'kaifior', 'nortais', 'terloir', 'ravraet', 'norzeen', 'finnaon', 'dexloon', 'belloal', 'lumcoal', 'belcoer', 'lumtaur', 'lykaix', 'arimien', 'silrain', 'finloir', 'quinmiet', 'tankiin', 'norfiir', 'marvaen', 'vexdies', 'belin', 'aritair', 'elyzeen', 'cordiar', 'kailoet', 'lyzeel', 'lymoor', 'zenneel', 'neoraer', 'zarreel', 'elylois', 'corcoes', 'zardiin', 'quinrias', 'felsaur', 'tankiel', 'kairiil', 'oranees', 'finneon', 'normiet', 'solzeil', 'norries', 'kaimoel', 'lumreil', 'solkaur', 'leofiix', 'vexloet', 'tanraas', 'silmies', 'darnaus', 'lykies', 'corrien', 'terriir', 'quinloin', 'sildior', 'oracoir', 'felleox', 'mircoas', 'finzeet', 'norrean', 'felkail', 'renmion', 'orarian', 'zarsuox', 'lumnaor', 'silnaen', 'felsuis', 'vexleus', 'valmier', 'kaikaor', 'tansuox', 'lymoon', 'solnaer', 'zarsuil', 'vexvaar', 'leosaon', 'elycoet', 'felsain', 'nornear', 'noron', 'leonair', 'belrian', 'felsuan', 'dexvaon', 'zardiix', 'dardiel', 'elysaox', 'darloan', 'felzeur', 'quindies', 'mirries', 'mirkion', 'zenlois', 'lummoer', 'leoreox', 'silmoes', 'silloox', 'solsuel', 'dares', 'darkien', 'valdiix', 'neofiel', 'darraer', 'valkaan', 'norur', 'silsuas', 'darnein', 'corvaar', 'neodiet', 'leocoon', 'finmiil', 'aricoal', 'solraon', 'silnein', 'ravleal', 'tansaix', 'ternaus', 'aervaix', 'tersaix', 'darsuix', 'feltaox', 'elyfiir', 'aerleer', 'kaitain', 'orakael', 'renlein', 'aerreor', 'elykaum', 'oranaox', 'zenil', 'jascoox', 'jaszeon', 'neomial', 'dexdius', 'mirmoor', 'rennais', 'finleur', 'tankaal', 'darsaix', 'tersues', 'lyleen', 'belmoes', 'ravfiis', 'valsaor', 'jasfiin', 'belcoon', 'quinsuur', 'valleal', 'corfien', 'renkaon', 'silsaes', 'valvaar', 'aerneen', 'solkien', 'corloas', 'solnaen', 'zenkium', 'ravdiet', 'mirmoes', 'aritaur', 'siltaor', 'corfial', 'zarmoen', 'felsual', 'zarreor', 'felfiir', 'terkion', 'felfies', 'tankaet', 'mirnaal', 'norriil', 'marreas', 'rencoet', 'silvaur', 'ariil', 'norsuer', 'neosaox', 'lumkius', 'rensuar', 'rentaix', 'dexnaes', 'darneet', 'zenleel', 'norkiox', 'valcous', 'mirer', 'sillein', 'belriis', 'marzeil', 'lummoox', 'elynaix', 'lumreer', 'zendien', 'mirreon', 'silsaon', 'rensuet', 'lumreis', 'aervaan', 'corfiur', 'aercoix', 'marraar', 'valzeen', 'quinreum', 'finrian', 'terkaal', 'silcois', 'ravdiel', 'lymoir', 'felzeor', 'elylous', 'dexzeox', 'dexmoum', 'norzeox', 'dexfiil', 'ravraon', 'silriar', 'vexloir', 'jaskaer', 'tervaas', 'solreer', 'sildial', 'lysaes', 'lumzeer', 'soldiel', 'zarkiox', 'kaimoum', 'quinsuil', 'ravsaal', 'soltail', 'felkaal', 'norlees', 'dextaox', 'marvaal', 'lyzeur', 'ravrean', 'jasmoes', 'felcour', 'corloir', 'quinvair', 'rencoum', 'rendien', 'lymoar', 'correum', 'arilous', 'darfian', 'zarrean', 'corneum', 'zarcoin', 'zarvaen', 'nordiox', 'tanmiis', 'vexriur', 'neoneon', 'marloir', 'neosuir', 'valriar', 'vexcoes', 'silsuus', 'kaireir', 'silkair', 'tersaum', 'norvaur', 'lydius', 'orair', 'rennaum', 'corleix', 'jasnaus', 'tandiix', 'zenreil', 'kaimior', 'cortaen', 'elymoon', 'zarraes', 'ravraan', 'tanleal', 'jasraet', 'mirfiix', 'noral', 'jaszeix', 'darloet', 'zarzeal', 'cordias', 'valkior', 'ravkair', 'feltais', 'darcoon', 'vexal', 'silkiox', 'lumtair', 'tertaar', 'aersais', 'zendiur', 'jasmoil', 'neoraus', 'dartaor', 'elysuen', 'aernail', 'tanzeus', 'mirnaus', 'arileer', 'norriis', 'kaisuer', 'ravfial', 'renraus', 'kairiix', 'zenrais', 'belraal', 'rencoil', 'leoraus', 'zenloil', 'tersael', 'orakiis', 'valraan', 'corloal', 'darcoir', 'valkaum', 'tanin', 'jasfies', 'zarkias', 'jasneal', 'quinnear', 'dexlear', 'leocoel', 'sildion', 'renleil', 'zenvaor', 'zardiel', 'ravkior', 'leodiil', 'tandiox', 'solcoin', 'markaas', 'silrias', 'dexneis', 'dexcoer', 'belmoon', 'norvaox', 'belnaar', 'ravsaix', 'cortaox', 'neokain', 'neozeil', 'leoir', 'kaidiin', 'martaen', 'lydiox', 'darkiin', 'quinsaan', 'zenmian', 'lumcoox', 'lumnair', 'kaior', 'renraox', 'darzeas', 'kailour', 'dexox', 'belmias', 'oralein', 'kaimien', 'felsuil', 'arimies', 'leodius', 'rensuer', 'norkaar', 'tervaon', 'dexrium', 'oravaon', 'zenkaon', 'aerlees', 'oravaox', 'ternail', 'aervaor', 'vexar', 'sildies', 'leoriet', 'oranail', 'tertaon', 'ravsuur', 'leokair', 'ravus', 'kaidier', 'arikium', 'ravdior', 'finsair', 'nortair', 'kaitaen', 'leoan', 'dexcoix', 'norrias', 'silfian', 'nornaur', 'darkius', 'belraon', 'lynees', 'zenraus', 'norrees', 'tersuis', 'silraor', 'quinkion', 'norneel', 'elykail', 'valzean', 'aernear', 'kaireel', 'zenzeox', 'quinnaum', 'finmoal', 'sollour', 'mardius', 'silleum', 'quinvaer', 'neokaur', 'orakiix', 'oradius', 'neodiur', 'vexkiix', 'dexvaas', 'marneor', 'lyfiil', 'cormien', 'belreel', 'tersuas', 'tanfias', 'marnaar', 'neofial', 'orakaer', 'tertaan', 'zarreur', 'zensais', 'valvaas', 'valnaer', 'quinreox', 'vexzeum', 'zarnaen', 'orasuan', 'dextain', 'finnaum', 'finfius', 'zarfiar', 'lytaes', 'dexzeur', 'orasuen', 'norriar', 'leonael', 'vexsuer', 'neolees', 'arineox', 'tanleox', 'zendias', 'kaifion', 'finraes', 'finloas', 'finrean', 'dexriir', 'aervaer', 'felraar', 'cornail', 'norloon', 'leofiil', 'zarraox', 'lyneal', 'vexvaur', 'mirsuon', 'lycoox', 'zarix', 'quinreir', 'darsuus', 'zenkiil', 'renvaes', 'lyriox', 'lumvaor', 'solrees', 'jasfien', 'tanloar', 'finneus', 'tanraes', 'zenon', 'tanmiet', 'corleir', 'aerrees', 'lumsaox', 'renreas', 'valneor', 'aerneur', 'dexriur', 'lumcous', 'valriix', 'zensaar', 'felfiix', 'darloes', 'zarcoet', 'neomoes', 'arifiir', 'dexraon', 'quinsaen', 'kaineil', 'corloes', 'darkiar', 'ariraor', 'lumreon', 'renfiis', 'terleix', 'silreas', 'finraal', 'marloin', 'norloel', 'felvais', 'mirvair', 'siltaum', 'norsuox', 'valmoon', 'vexzeox', 'nornean', 'ravcoin', 'tersuir', 'ravkaix', 'neoriet', 'renmier', 'jassain', 'cordiis', 'belon', 'leoreon', 'vexfiis', 'marsues', 'mirneil', 'kailees', 'norneas', 'terkain', 'tancoor', 'valfiox', 'termoen', 'belcous', 'quinsuis', 'leoal', 'leodiet', 'lysaix', 'darkion', 'vexleor', 'tandium', 'terdiox', 'corneal', 'norreer', 'belleox', 'cormoar', 'aernain', 'belkion', 'jasrear', 'quincoet', 'corneer', 'kaimiox', 'zarsaix', 'aritaen', 'oramoet', 'terriin', 'terleum', 'norvail', 'cortaet', 'belus', 'renen', 'leovaon', 'zarcoix', 'tervaan', 'solrian', 'felneus', 'dextaum', 'lumdien', 'finmoir', 'zarkaox', 'elysael', 'dexmiis', 'darvaen', 'kaier', 'aermiis', 'finloor', 'soldion', 'corkiar', 'vexsuis', 'terraus', 'dextaen', 'sildiet', 'oradion', 'neoloes', 'nornaox', 'zarkier', 'orafias', 'ravkiel', 'kaikain', 'mirsaox', 'felsuum', 'aersual', 'neotaet', 'felleal', 'tertaen', 'neomies', 'finzeis', 'leokael', 'valrair', 'aricoox', 'norriix', 'aerkaur', 'zenreum', 'lyreer', 'darreas', 'cormour', 'vexrein', 'leovaas', 'zarsuel', 'quinzein', 'silvaal', 'valvaon', 'neomoan', 'norloal', 'renrius', 'silmiar', 'silmoil', 'aermoet', 'silmoer', 'lumvaar', 'felmous', 'valnaum'}
