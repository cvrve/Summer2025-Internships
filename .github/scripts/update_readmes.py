from datetime import datetime
import util


def main():

    listings = util.getListingsFromJSON()

    # split up listings into summer and off-season
    # TODO: add new grads
    summer_listings = [listing for listing in listings if listing["season"] == "Summer"]
    offseason_listings = [listing for listing in listings if listing["season"] != "Summer"]

    # validate listings
    util.checkSchema(summer_listings)
    util.checkSchema(offseason_listings)

    # sort listings
    summer_listings = util.sortListings(summer_listings) # no longer in place my bad :(
    offseason_listings = util.sortListings(offseason_listings)

    # create table and embed
    util.embedTable(summer_listings, "README.md", False)
    util.embedTable(offseason_listings, "OFFSEASON_README.md", True)

    util.setOutput("commit_message", "Updating READMEs at " + datetime.now().strftime("%B %d, %Y %H:%M:%S"))


if __name__ == "__main__":
    main()
