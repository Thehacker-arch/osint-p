from fastapi import APIRouter # type: ignore
from app.collectors.social_media import SocialMediaCollector
from app.services.graph_service import GraphService
from app.models import Person, SocialMediaProfile, SearchResult, Link
from app import db

router = APIRouter()

@router.get("/search/{username}")
def search(username: str):
    collector = SocialMediaCollector()
    graph = GraphService()
    
    accounts = []

    github = collector.get_full_profile(username)
    insta = collector.fetch_instagram(username)
    twitter = collector.fetch_twitter(username)

    instadata = collector.parse_instagram_bio(insta) if insta else None


    emails = [github.get("email")] if github and github.get("email") else []
    # person_id = collector.resolve_person_id(username, github=github, insta=instadata, twitter=twitter, links=github.get("links", []) if github else [])
    
    all_new_links = set()
    if github: all_new_links.update(github.get("links", []))
    if twitter: all_new_links.update(twitter.get("links", []))
    if instadata: all_new_links.update(instadata['links'])
    BASE_URLS = ["https://github.com", "https://x.com", "https://twitter.com", "https://linkedin.com", "https://instagram.com"]
    
    # normalized_new_links = [collector.normalize_links(l) for l in all_new_links if l]
    # normalized_new_links = [l for l in normalized_new_links if l not in BASE_URLS]

    # normalized_new_links = list(set(filter(None, normalized_new_links)))
    
    expanded = set()
    for l in all_new_links:
        if l and "t.co" in l:
            expanded.add(collector.expand_url(l))
        elif l:
            expanded.add(l)

    normalized_new_links = list(set(filter(None, [
        collector.normalize_links(l) for l in all_new_links if l
    ])))
    normalized_new_links = [l for l in normalized_new_links if l not in BASE_URLS]

    existing_id = None
    if github:
        links_gh = [collector.normalize_links(link) for link in github.get("links", [])]
        existing_id = db.find_person_by_pivot("github", github['username'])
    
    if not existing_id and twitter:
        links_tw = [collector.normalize_links(link) for link in twitter.get("links", [])]
        existing_id = db.find_person_by_pivot("twitter", twitter['username'])
    
    if not existing_id and instadata:
        links_insta = [collector.normalize_links(link) for link in instadata['links']]
        existing_id = db.find_person_by_pivot("instagram", instadata['username'])

    pending_possible_match = None
    # If we found an ID via a link pivot, FORCIBLY use that ID
    if existing_id:
        person_id = existing_id
        print(f"PIVOT MATCH: Merging into existing ID {existing_id}")
    
    else:
        candidate_persons = []
        seen_ids = set()
        for link in normalized_new_links:
            found = db.find_person_by_link(link)
            if found and found["id"] not in seen_ids:
                if any(domain in link for domain in ["github.com", "linkedin.com"]):
                    person_id = found_acc["id"]
                    print(f"ACCOUNT URL MATCH: {link} → {person_id}")
                    existing_id = person_id  # treat like a pivot match
                    break
                candidate_persons.append(found)
                seen_ids.add(found["id"])
            
            found_acc = db.find_person_by_account_url(link)
            if found_acc and found_acc["id"] not in seen_ids:
                candidate_persons.append(found_acc)
                seen_ids.add(found_acc["id"])
        
        current_name = github.get("name") if github else (twitter.get("name") if twitter else (instadata["name"] if instadata else None))
        # current_name_normalized = current_name.strip().lower() if current_name else None
        # candidate_persons.extend(db.find_persons_by_username(current_name, name=current_name))
        if current_name:
            for c in db.find_persons_by_username(username, name=current_name):
                if c["id"] not in seen_ids:
                    candidate_persons.append(c)
                    seen_ids.add(c["id"])

        score = 0.0
        best_match_id = None
        new_profile_data = {
            "name": github.get("name") if github else (instadata["name"] if instadata else None),
            "bio": github.get("bio") if github else (instadata["description"] if instadata else None),
            "location": twitter.get("location") if twitter else None,
            "links": normalized_new_links
        }

        for candidate in candidate_persons:
            confidence = graph.confidence_score(candidate, new_profile_data)
            if confidence > score:
                score = confidence
                best_match_id = candidate["id"]
        
        if best_match_id and score >= 0.5:
            person_id = best_match_id
            print(f"MATCH FOUND: Linking to existing person {person_id} (Conf: {score})")
        else:
            if github:
                person_id = f"github:{github.get('username').lower()}"
            elif twitter:
                person_id = f"twitter:{twitter.get('username').lower()}"
            elif instadata: 
                person_id = f"instagram:{instadata['username'].lower()}"
            else:
                person_id = f"identity:{username.lower()}"

            print(f"NEW IDENTITY: Creating separate person node (Conf: {score})")

            if best_match_id and 0.3 <= score < 0.5:
                pending_possible_match = (best_match_id, score)
                # db.link_as_possible_match(best_match_id, person_id, score)
                # print(f"DOUBTFUL MATCH: Created link between {person_id} and {best_match_id}")


    person = Person(
        id=person_id,
        username=username,
        name=None,
        bio=None,
        emails=emails,
        location=None
    )

    if github:
        # links = github.get("links", [])
        links = [collector.normalize_links(link) for link in github.get("links", [])]
        person.name = github.get("name") or person.name
        person.bio = github.get("bio") or person.bio
        gh_acc = SocialMediaProfile(
            platform="github",
            username=github.get("username"),
            followers=github.get("followers"),
            following=github.get("following"),
            posts=github.get("posts")
        )
        graph.create_person(person, gh_acc, links_list=links)
        accounts.append(gh_acc)


    if insta:
        if instadata:
            links_insta = [collector.normalize_links(link) for link in instadata.get("links", [])]
            print(f"DEBUG: final person_id = {person_id}")
            person.name = instadata["name"] or person.name
            person.bio = instadata["description"] or person.bio
            insta_acc = SocialMediaProfile(**instadata)
            print(f"DEBUG: created person {person.id} with account {insta_acc.platform}:{insta_acc.username}")
            graph.create_person(person, insta_acc, links_list=links_insta)
            accounts.append(insta_acc)
    print(f"DEBUG instadata: {instadata}")

    if twitter:
        person.name = twitter.get("name") or person.name
        person.bio = twitter.get("bio") or person.bio
        person.location = twitter.get("location") or person.location

        twitter_acc = SocialMediaProfile(
            platform="twitter",
            username=twitter.get("username"),
            followers=twitter.get("followers"),
            following=twitter.get("following"),
            posts=twitter.get("posts")
        )
        
        twitter_links = [collector.normalize_links(link) for link in twitter.get("links", [])]
        graph.create_person(person, twitter_acc, links_list=twitter_links)
        accounts.append(twitter_acc)

    # pending_possible_match = None
    if pending_possible_match:
        match_id, match_score = pending_possible_match
        db.link_as_possible_match(match_id, person_id, match_score)
        print(f"DOUBTFUL MATCH: {person_id} ↔ {match_id} (conf: {match_score})")

    # Change reconcile call at bottom of search.py
    graph.reconcile_all(current_person_id=person_id, 
                        current_links=normalized_new_links,
                        current_name=person.name)    
    return {"data": accounts}