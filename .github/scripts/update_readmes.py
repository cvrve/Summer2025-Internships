from datetime import datetime
import util


def main():

    listings = util.getListingsFromJSON()

    util.checkSchema(listings)
    listings = util.sortListings(listings) # no longer in place my bad :(
    util.embedTable(listings, "README.md")

    util.setOutput("commit_message", "Updating READMEs at " + datetime.now().strftime("%B %d, %Y %H:%M:%S"))


if __name__ == "__main__":
    main()
