from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def get_session():
    return driver.session()

def find_persons_by_username(username, name=None):
    query = """
    MATCH (p:Person)
    OPTIONAL MATCH (p)-[:HAS_ACCOUNT]->(a:SocialMediaProfile)
    WITH p, a
    WHERE toLower(a.username) = toLower($username)
       OR ($name IS NOT NULL AND toLower(p.name) = toLower($name))
       OR toLower($username) IN [x IN coalesce(p.aliases, []) | toLower(x)]
    RETURN DISTINCT p {
        .id, .name, .bio, .location,
        links: [(p)-[:HAS_LINK]->(l) | l.url]
    } as person_data
    """
    with get_session() as session:
        result = session.run(query, {"username": username, "name": name})
        return [record["person_data"] for record in result]
    
def link_as_possible_match(id1, id2, score):
        query = """
        MATCH (p1:Person {id: $id1}), (p2:Person {id: $id2})
        MERGE (p1)-[r:POSSIBLY_SAME_AS]-(p2)
        SET r.confidence = $score, r.updated_at = timestamp()
        RETURN r
        """
        with get_session() as session:
            result = session.run(query, {"id1": id1, "id2": id2, "score": score})
            record = result.single()
            if record:
                print(f"DEBUG: POSSIBLY_SAME_AS created between {id1} and {id2}")
            else:
                print(f"DEBUG: POSSIBLY_SAME_AS failed — one or both nodes missing")

def find_person_by_link(url):
    query = """
    MATCH (l:Link {url: $url})<-[:HAS_LINK]-(p:Person)
    RETURN p { .id, .name, .bio, .location, links: [(p)-[:HAS_LINK]->(link) | link.url] } as person_data
    LIMIT 1
    """
    with get_session() as session:
        result = session.run(query, {"url": url})
        record = result.single()
        print(f"DEBUG find_person_by_link({url}): {'HIT' if record else 'MISS'}")
        return record["person_data"] if record else None

def find_person_by_account_url(url):
    query = """
    MATCH (p:Person)-[:HAS_ACCOUNT]->(a:SocialMediaProfile)
    WHERE toLower(a.url) = toLower($url)
    RETURN p { .id, .name, .bio, .location, 
               links: [(p)-[:HAS_LINK]->(l) | l.url] } as person_data
    LIMIT 1
    """
    with get_session() as session:
        result = session.run(query, {"url": url})
        record = result.single()
        print(f"DEBUG find_person_by_account_url({url}): {'HIT' if record else 'MISS'}")
        return record["person_data"] if record else None
    
def find_person_by_pivot(platform, username):
    # This query looks for a Person who:
    # 1. Already has this specific social media account
    # 2. OR has a Link node pointing to this account's URL
    query = """
    MATCH (p:Person)-[:HAS_ACCOUNT]->(a:SocialMediaProfile)
    WHERE a.platform = $platform AND a.username = $username
    
    RETURN p.id as id LIMIT 1
    """
    with get_session() as session:
        result = session.run(query, {
            "platform": platform,
            "username": username
        })
        record = result.single()
        if record:
            print(f"DEBUG: PIVOT SUCCESS! Found ID: {record['id']}")
            return record["id"]
        print(f"DEBUG: PIVOT FAILED for {username}")
        return None

# def find_all_persons():
#     query = """
#     MATCH (p:Person)
#     RETURN p {
#         .id, .name, .bio, .location,
#         links: [(p)-[:HAS_LINK]->(l) | l.url],
#         emails: [(p)-[:HAS_EMAIL]->(e) | e.address],
#         accounts: [(p)-[:HAS_ACCOUNT]->(a) | a.url]
#     } as person_data
#     """
#     with get_session() as session:
#         result = session.run(query)
#         return [record["person_data"] for record in result]
    
def find_all_persons():
    query = """
    MATCH (p:Person)
    RETURN p {
        .id, .name, .bio, .location,
        links: [(p)-[:HAS_LINK]->(l) | l.url],
        accounts: [(p)-[:HAS_ACCOUNT]->(a) | a.url]
    } as person_data
    """
    with get_session() as session:
        result = session.run(query)
        return [record["person_data"] for record in result]

def merge_persons(winner_id, loser_id):
    """Repoint all of loser's relationships to winner, then delete loser."""
    query = """
    MATCH (winner:Person {id: $winner_id})
    MATCH (loser:Person {id: $loser_id})
    WHERE winner <> loser

    WITH winner, loser
    OPTIONAL MATCH (loser)-[:HAS_ACCOUNT]->(a:SocialMediaProfile)
    WITH winner, loser, collect(a) as accounts
    FOREACH (a IN accounts | MERGE (winner)-[:HAS_ACCOUNT]->(a))

    WITH winner, loser
    OPTIONAL MATCH (loser)-[:HAS_LINK]->(l:Link)
    WITH winner, loser, collect(l) as links
    FOREACH (l IN links | MERGE (winner)-[:HAS_LINK]->(l))

    WITH winner, loser
    OPTIONAL MATCH (loser)-[:HAS_EMAIL]->(e:Email)
    WITH winner, loser, collect(e) as emails
    FOREACH (e IN emails | MERGE (winner)-[:HAS_EMAIL]->(e))

    WITH winner, loser
    SET winner.aliases = REDUCE(s = coalesce(winner.aliases, []), 
                                x IN coalesce(loser.aliases, []) | 
                                CASE WHEN x IN s THEN s ELSE s + x END)
    SET winner.aliases = REDUCE(s = coalesce(winner.aliases, []),
                                x IN [loser.id] |
                                CASE WHEN x IN s THEN s ELSE s + x END)

    SET winner.name = coalesce(winner.name, loser.name)
    SET winner.bio = coalesce(winner.bio, loser.bio)
    SET winner.location = coalesce(winner.location, loser.location)

    WITH winner, loser
    DETACH DELETE loser

    RETURN winner.id as merged_id
    """
    with get_session() as session:
        result = session.run(query, {"winner_id": winner_id, "loser_id": loser_id})
        record = result.single()
        if record:
            print(f"MERGED: {loser_id} → {winner_id}")
        else:
            print(f"MERGE FAILED: {winner_id} or {loser_id} not found")