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
    "sponsorship": 9,
    "active": 11,
    "email": 13,
    "email_is_edit": 15
}

# lines that require special handling
SPECIAL_LINES = set(["url", "locations", "sponsorship", "active", "email", "email_is_edit"])

def add_https_to_url(url):
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def getData(body, is_edit, username):
    lines = [text.strip("# ") for text in re.split('[\n\r]+', body)]
    
    data = {"date_updated": int(datetime.now().timestamp())}

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

    if not new_internship and not edit_internship:
        util.fail("Only new_internship and edit_internship issues can be approved")


    # GET DATA FROM ISSUE FORM

    issue_body = event_data['issue']['body']
    issue_user = event_data['issue']['user']['login']

    data = getData(issue_body, is_edit=edit_internship, username=issue_user)

    if new_internship:
        data["source"] = issue_user
        data["id"] = str(uuid.uuid4())
        data["date_posted"] = int(datetime.now().timestamp())
        data["company_url"] = ""
        data["is_visible"] = True

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
