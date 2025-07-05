import json
import sys
import uuid
from datetime import datetime
import util
import re

# TODO: fix this object display comment formatting
# ["Company Name", "_No response_", "Internship Title", "_No response_", "Link to Internship Posting", "example.com/link/to/posting", "Location", "San Franciso, CA | Austin, TX | Remote"]
LINES = {
    "url": 1,
    "company_name": 3,
    "title": 5,
    "locations": 7,
    "season": 9,
    "sponsorship": 11,
    "active": 13,
    "email": 15,
    "email_is_edit": 17
}

# Lines for close_internship form
CLOSE_LINES = {
    "company_name": 1,
    "role_title": 3,
    "job_url": 5,
    "closure_reason": 7,
    "additional_info": 9
}

# lines that require special handling
SPECIAL_LINES = set(["url", "locations", "sponsorship", "active", "email", "email_is_edit"])

def add_https_to_url(url):
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def getData(body, is_edit, is_close, username):
    lines = [text.strip("# ") for text in re.split('[\n\r]+', body)]
    
    data = {"date_updated": int(datetime.now().timestamp())}

    if is_close:
        # Handle close internship form
        if "no response" not in lines[CLOSE_LINES["company_name"]].lower():
            data["company_name"] = lines[CLOSE_LINES["company_name"]].strip()
        if "no response" not in lines[CLOSE_LINES["role_title"]].lower():
            data["role_title"] = lines[CLOSE_LINES["role_title"]].strip()
        if "no response" not in lines[CLOSE_LINES["job_url"]].lower():
            data["job_url"] = add_https_to_url(lines[CLOSE_LINES["job_url"]].strip())
        if "no response" not in lines[CLOSE_LINES["closure_reason"]].lower():
            data["closure_reason"] = lines[CLOSE_LINES["closure_reason"]].strip()
        
        # Set default email for close operations
        util.setOutput("commit_email", "action@github.com")
        util.setOutput("commit_username", "GitHub Action")
        return data

    # url handling
    if "no response" not in lines[ LINES["url"] ].lower():
        data["url"] = add_https_to_url(lines[ LINES["url"] ].strip())

    # location handling
    if "no response" not in lines[ LINES["locations"] ].lower():
        data["locations"] = [line.strip() for line in lines[ LINES["locations"] ].split("|")]

    # sponsorship handling
    if "no response" not in lines[ LINES["sponsorship"] ].lower():
        data["sponsorship"] = "Other"
        for option in ["Offers Sponsorship", "Does Not Offer Sponsorship", "U.S. Citizenship is Required"]:
            if option in lines[ LINES["sponsorship"] ]:
                data["sponsorship"] = option

    # active handling
    if "none" not in lines[ LINES["active"] ].lower():
        data["active"] = "yes" in lines[ LINES["active"] ].lower()

    # regular field handling (company_name, etc.)
    for title, line_index in LINES.items():
        if title in SPECIAL_LINES: continue
        content = lines[line_index]

        if "no response" not in content.lower():
            data[title] = content

    # email handling
    if is_edit:
        data["is_visible"] = "[x]" not in lines[15].lower()
    email = lines[ LINES["email_is_edit"] if is_edit else LINES["email"] ].lower()
    if "no response" not in email:
        util.setOutput("commit_email", email)
        util.setOutput("commit_username", username)
    else:
        util.setOutput("commit_email", "action@github.com")
        util.setOutput("commit_username", "GitHub Action")
    
    return data


def main():
    event_file_path = sys.argv[1]

    with open(event_file_path) as f:
        event_data = json.load(f)


    # CHECK IF NEW OR OLD INTERNSHIP

    new_internship = "new_internship" in [label["name"] for label in event_data["issue"]["labels"]]
    edit_internship = "edit_internship" in [label["name"] for label in event_data["issue"]["labels"]]
    close_internship = "close_internship" in [label["name"] for label in event_data["issue"]["labels"]]

    if not new_internship and not edit_internship and not close_internship:
        util.fail("Only new_internship, edit_internship, and close_internship issues can be approved")


    # GET DATA FROM ISSUE FORM

    issue_body = event_data['issue']['body']
    issue_user = event_data['issue']['user']['login']

    data = getData(issue_body, is_edit=edit_internship, is_close=close_internship, username=issue_user)

    if new_internship:
        data["source"] = issue_user
        data["id"] = str(uuid.uuid4())
        data["date_posted"] = int(datetime.now().timestamp())
        data["company_url"] = ""
        data["is_visible"] = True

    if not close_internship:
        # remove utm-source
        utm = data["url"].find("?utm_source")
        if utm == -1:
            utm = data["url"].find("&utm_source")
        if utm != -1:
            data["url"] = data["url"][:utm]


    # UPDATE LISTINGS

    def get_commit_text(listing):
        closed_text = "" if listing["active"] else "(Closed)"
        sponsorship_text = "" if listing["sponsorship"] == "Other" else ("(" + listing["sponsorship"] + ")")
        listing_text = (listing["title"].strip() + " at " + listing["company_name"].strip() + " " + closed_text + " " + sponsorship_text).strip()
        return listing_text

    with open(".github/scripts/listings.json", "r") as f:
        listings = json.load(f)

    if close_internship:
        # Handle closing internship by company name, role title, and optionally URL
        company_name = data.get("company_name")
        role_title = data.get("role_title")
        job_url = data.get("job_url")
        
        if not company_name or not role_title:
            util.fail("Company name and role title are required to close an internship")
        
        # Find matching listings
        candidates = []
        for item in listings:
            if (item["company_name"].lower() == company_name.lower() and 
                item["title"].lower() == role_title.lower()):
                candidates.append(item)
        
        # If URL provided, filter by URL
        if job_url and candidates:
            url_matches = [item for item in candidates if item["url"] == job_url]
            if url_matches:
                candidates = url_matches
        
        if not candidates:
            util.fail(f"No internship found matching company '{company_name}' and role '{role_title}'")
        elif len(candidates) > 1:
            util.fail(f"Multiple internships found matching company '{company_name}' and role '{role_title}'. Please provide the job URL to specify which one to close.")
        
        listing_to_close = candidates[0]
        
        # Mark as inactive and update timestamp
        listing_to_close["active"] = False
        listing_to_close["date_updated"] = data["date_updated"]
        
        util.setOutput("commit_message", "closed listing: " + get_commit_text(listing_to_close))
    else:
        if listing_to_update := next(
            (item for item in listings if item["url"] == data["url"]), None
        ):
            if new_internship:
                util.fail("This internship is already in our list. See CONTRIBUTING.md for how to edit a listing")
            for key, value in data.items():
                listing_to_update[key] = value

            util.setOutput("commit_message", "updated listing: " + get_commit_text(listing_to_update))
        else:
            if edit_internship:
                util.fail("We could not find this internship in our list. Please double check you inserted the right url")
            listings.append(data)

            util.setOutput("commit_message", "added listing: " + get_commit_text(data))

    with open(".github/scripts/listings.json", "w") as f:
        f.write(json.dumps(listings, indent=4))


if __name__ == "__main__":
    main()
