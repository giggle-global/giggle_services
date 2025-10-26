import random

# Short, pronounceable fragments (no more than 3 syllables when combined)
prefixes = [
    "zen", "lum", "vex", "sol", "neo", "kai", "ari", "ely", "ora", "dex",
    "fin", "mir", "ren", "nor", "val", "aer", "cor", "ly", "zar", "tan",
    "bel", "quin", "ter", "rav", "sil", "dar", "jas", "leo", "mar", "fel"
]

middles = [
    "", "lo", "ra", "ri", "ta", "na", "mi", "ka", "sa", "di",
    "co", "ne", "le", "re", "ze", "va", "fi", "mo", "su", "ki"
]

suffixes = [
    "on", "or", "us", "en", "an", "ix", "is", "er", "ar", "in",
    "ox", "um", "et", "es", "as", "il", "el", "al", "ir", "ur"
]

# Combine random syllables
usernames = set()
while len(usernames) < 1000:
    base = random.choice(prefixes) + random.choice(middles) + random.choice(suffixes)
    usernames.add(base.lower())

# usernames is a set of 1000 unique short names
print(len(usernames), "unique base usernames generated.")
print(usernames)