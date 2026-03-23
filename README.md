# OSINT Platform

An intelligent Open Source Intelligence (OSINT) platform for discovering, linking, and analyzing digital identities across multiple data sources.


## Overview

This project is designed to go beyond basic scraping.

Instead of just collecting data, it focuses on:

* Identity resolution
* Cross-platform correlation
* Graph-based relationship mapping

The goal is to answer:

> “Do these multiple usernames, profiles, and signals belong to the same person?”


## Core Features

* Username & profile search across platforms (Twitter/X, Instagram, GitHub), more to be added.
* Identity matching and confidence scoring
* Graph-based linking of entities (Person ↔ Accounts)
* Data extraction (bio, location, links, etc.) which can be used to link accounts of same person.
* Backend built with **FastAPI**


## Tech Stack

* Backend: Python FastAPI
* Scraping: Playwright / Requests
* Database: Neo4j
* Frontend: Yet to be done
* Others: ML to be added to make the system more intelligent.

---

## Problem It Solves

Most OSINT tools:

* Show raw data
* Don’t verify identity connections

This leads to:

* False linking of profiles
* Confusion between similar usernames

This platform tries to solve problems like:
* Linking multiple accounts to the person it belongs to
* Improving identity confidence
* Structuring intelligence clearly


## Current Challenges

* Handling duplicate usernames across platforms (sometimes it links accounts with same username to same person, while it's not)
* Avoiding incorrect identity merges
* Improving confidence scoring logic


## Roadmap (Thing that will be added in the future)

* Add Machine Learning for furthur analysis.
* Add more Data Scraping sources, like DNS, domain searches, public/leaked databases, OSINT search engine APIs, TOR search results and maybe company registration or filings.
* Add a frontend.


## Setup

```bash
git clone https://github.com/yourusername/osint-platform.git
cd osint-platform
pip install -r requirements.txt
uvicorn app:app --reload
(make a virtual env- recommended)
```


## Example Use Case

Input:

```
username: _username (for example)
```

Output:

* Linked Twitter account
* Linked Instagram account
* Linked GitHub account
* Extracted bio + metadata
* Confidence score of identity match & graph linking in Neo4j (between the accounts linked to a person's name exatracted)

It can also link two same person if the bio of two different accounts is similar or if any links are extracted (which corresponds to previous searched
usernames or accounts)
