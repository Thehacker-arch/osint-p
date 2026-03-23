from app.db import get_session
from app import db
from difflib import SequenceMatcher

class GraphService:
    def __init__(self):
        self.session = get_session()
    
    def close(self):
        self.session.close()

    def create_person(self, person, account, links_list=None):
            emails_list = person.emails if isinstance(person.emails, list) else []
            links_list = links_list or []

            query="""
            MERGE (p:Person {id: $id})
            SET p.name     = CASE WHEN p.name IS NULL AND $name IS NOT NULL 
                                THEN $name ELSE p.name END,
                p.bio      = CASE WHEN p.bio IS NULL AND $bio IS NOT NULL 
                                THEN $bio ELSE p.bio END,
                p.location = CASE WHEN p.location IS NULL AND $location IS NOT NULL 
                                THEN $location ELSE p.location END
            
            WITH p
            SET p.aliases = [x IN (coalesce(p.aliases, []) + $username) WHERE x IS NOT NULL]
            WITH p
            SET p.aliases = REDUCE(s = [], x IN p.aliases | CASE WHEN x IN s THEN s ELSE s + x END)


            MERGE (a:SocialMediaProfile {
                platform: $platform,
                username: $acc_username
            })
            
            SET a.followers = $followers,
                a.following = $following,
                a.posts = $posts,
                a.url = $url

            MERGE (p)-[:HAS_ACCOUNT]->(a)

            WITH p
            FOREACH (email_addr IN $emails_list |
                MERGE (e:Email {address: email_addr})
                MERGE (p)-[:HAS_EMAIL]->(e)
            )

            WITH p
            FOREACH (link_url IN $links_list |
                MERGE (l:Link {url: link_url})
                MERGE (p)-[:HAS_LINK]->(l)
            )
            """

            with get_session() as session:
                session.run(query, {
                    "id": person.id,
                    "username": person.username,
                    "name": person.name,
                    "bio": person.bio,
                    "location": person.location,

                    "emails_list": emails_list,
                    "links_list": links_list,

                    "acc_username": account.username,
                    "platform": account.platform,
                    "followers": account.followers,
                    "following": account.following,
                    "posts": account.posts,
                    "url": f"https://{account.platform}.com/{account.username.lower()}"
                })


    def get_or_create_person(self, username):
        person = db.find_persons_by_username(username.lower().strip())
        if person:
            return person
        return db.create_person(username)
    
    @staticmethod
    def get_similarity(a, b):
        if not a or not b: return 0.0
        return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()
    
    def confidence_score(self, person_a, person_b):
        score = 0.0
        link_a = set(person_a.get("links", []))
        link_b = set(person_b.get("links", []))

        shared_links = link_a.intersection(link_b)
        
        if any("linkedin.com" in l or "vercel.app" in l or "github.com" in l for l in shared_links):
            return 1.0
        
        if shared_links:
            score += 0.6
        
        name_similarity = self.get_similarity(person_a.get("name"), person_b.get("name"))
        if person_a.get("name") and person_b.get("name") and len(person_a.get("name")) > 3 and len(person_b.get("name")) > 3:
            if name_similarity < 0.6:
                return 0.0
        score += name_similarity * 0.4

        bio_similarity = self.get_similarity(person_a.get("bio"), person_b.get("bio"))
        score += bio_similarity * 0.2

        location_similarity = self.get_similarity(person_a.get("location"), person_b.get("location"))
        score += location_similarity * 0.2

        if person_a.get("emails") and person_b.get("emails"):
            email_similarity = self.get_similarity(",".join(person_a.get("emails")), 
                                                   ",".join(person_b.get("emails")))
            score += email_similarity * 0.1

        print(f"DEBUG CONFIDENCE: comparing '{person_a.get('name')}' vs '{person_b.get('name')}'")

        return round(score, 2)
    
    def reconcile_all(self, current_person_id=None, current_links=None, current_name=None):
        persons = db.find_all_persons()
        merged = set()
        print(f"DEBUG RECONCILE: {len(persons)} persons in DB: {[p['id'] for p in persons]}")

        WEAK_DOMAINS = {
            "instagram.com", "twitter.com", "x.com",
            "github.com", "facebook.com", "tiktok.com"
        }

        # If we have fresh scraped data, check it against all existing persons first
        if current_person_id and current_links:
            current_link_set = set(current_links)
            for person in persons:
                if person["id"] == current_person_id:
                    continue
                if person["id"] in merged:
                    continue

                stored_links = set(person.get("links", []) + person.get("accounts", []))
                shared = current_link_set.intersection(stored_links)
                
                strong_shared = {
                    l for l in shared
                    if not any(domain in l for domain in WEAK_DOMAINS)
                }

                if strong_shared:
                    print(f"RECONCILE (fresh): {current_person_id} matches {person['id']} via {strong_shared}")
                    db.merge_persons(person["id"], current_person_id)
                    merged.add(current_person_id)
                    return  # current person was merged, stop

                # Also score using fresh name
                candidate_data = {
                    "name": current_name,
                    "links": list(current_link_set)
                }
                score = self.confidence_score(person, candidate_data)
                print(f"RECONCILE (fresh) score: {current_person_id} vs {person['id']} = {score}")
                if score >= 0.5:
                    db.merge_persons(person["id"], current_person_id)
                    merged.add(current_person_id)
                    return

        # Then do the standard all-pairs check
        for i, person_a in enumerate(persons):
            if person_a["id"] in merged:
                continue
            for person_b in persons[i+1:]:
                if person_b["id"] in merged:
                    continue

                links_a = set(person_a.get("links", []) + person_a.get("accounts", []))
                links_b = set(person_b.get("links", []) + person_b.get("accounts", []))
                shared = links_a.intersection(links_b)

                strong_shared = {
                    l for l in shared
                    if not any(domain in l for domain in WEAK_DOMAINS)
                }

                if strong_shared:
                    print(f"RECONCILE: {person_a['id']} + {person_b['id']} via {strong_shared}")
                    db.merge_persons(person_a["id"], person_b["id"])
                    merged.add(person_b["id"])
                    continue

                score = self.confidence_score(person_a, person_b)
                print(f"RECONCILE SCORE: {person_a['id']} vs {person_b['id']} = {score}")
                if score >= 0.5:
                    db.merge_persons(person_a["id"], person_b["id"])
                    merged.add(person_b["id"])
        
    # def reconcile_all(self):
    #     """After every search, check if any existing persons should now be merged."""
    #     persons = db.find_all_persons()
    #     merged = set()  # track IDs that have been absorbed

    #     for i, person_a in enumerate(persons):
    #         if person_a["id"] in merged:
    #             continue
    #         for person_b in persons[i+1:]:
    #             if person_b["id"] in merged:
    #                 continue
    #             if person_a["id"] == person_b["id"]:
    #                 continue

    #             # Check shared links (including account URLs)
    #             links_a = set(person_a.get("links", []) + person_a.get("accounts", []))
    #             links_b = set(person_b.get("links", []) + person_b.get("accounts", []))
    #             shared = links_a.intersection(links_b)

    #             if shared:
    #                 # Any shared link = definite same person
    #                 winner_id = person_a["id"]
    #                 loser_id = person_b["id"]
    #                 db.merge_persons(winner_id, loser_id)
    #                 merged.add(loser_id)
    #                 print(f"RECONCILE: merged {loser_id} into {winner_id} via shared link: {shared}")
    #                 continue

    #             score = self.confidence_score(person_a, person_b)
    #             if score >= 0.5:
    #                 winner_id = person_a["id"]
    #                 loser_id = person_b["id"]
    #                 db.merge_persons(winner_id, loser_id)
    #                 merged.add(loser_id)
    #                 print(f"RECONCILE: merged {loser_id} into {winner_id} (conf: {score})")