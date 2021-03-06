import logging
from flexget.entry import Entry
from flexget.plugin import internet, register_plugin
from flexget.utils.tools import urlopener

timeout = 10
import socket
socket.setdefaulttimeout(timeout)

log = logging.getLogger('nzbmatrix')


class NzbMatrix(object):
    """NZBMatrix search plugin."""

    def validator(self):
        from flexget import validator
        nzbmatrix = validator.factory('dict')
        nzbmatrix.accept('integer', key='catid')
        nzbmatrix.accept('integer', key='num')
        nzbmatrix.accept('integer', key='age')
        nzbmatrix.accept('choice', key='region').accept_choices(
            ['1', '2', '3', 'PAL', 'NTSC', 'FREE'], ignore_case=True)
        nzbmatrix.accept('text', key='group')
        nzbmatrix.accept('text', key='username', required=True)
        nzbmatrix.accept('text', key='apikey', required=True)
        nzbmatrix.accept('integer', key='larger')
        nzbmatrix.accept('integer', key='smaller')
        nzbmatrix.accept('integer', key='minhits')
        nzbmatrix.accept('integer', key='maxhits')
        nzbmatrix.accept('integer', key='maxage')
        nzbmatrix.accept('boolean', key='englishonly')
        # TODO: I should overwrite this below. If there's an IMDB ID, I should
        # search on it via weblink
        nzbmatrix.accept('choice', key='searchin').accept_choices(
            ['name', 'subject', 'weblink'], ignore_case=True)
        return nzbmatrix

    # Search plugin API
    def search(self, query, comparator, config=None):
        # TODO: Implement comparator matching
        import urllib
        params = self.getparams(config)
        params['search'] = self.clean(query)
        search_url = 'https://api.nzbmatrix.com/v1.1/search.php?' + urllib.urlencode(params)
        results = self.nzbid_from_search(search_url, params['search'], query)
        if not results:
            return []
        else:
            entries = []
            for result in results:
                entry = Entry()
                entry['title'] = result['NZBNAME']
                download_params = {"username": params['username'], 'apikey': params['apikey'], 'id': result['NZBID']}
                entry['url'] = "http://api.nzbmatrix.com/v1.1/download.php?" + urllib.urlencode(download_params)
                entries.append(entry)
            return entries

    def getparams(self, config):
        # keeping vars separate, for code readability. Config entries are
        # identical to params passed.
        params = config
        if 'searchin' in params:
            params['searchin'] = params['searchin'].lower()
        if 'region' in params:
            if params['region'].lower() == 'pal':
                params['region'] = 1
            if params['region'].lower() == 'ntsc':
                params['region'] = 2
            if params['region'].lower() == 'free':
                params['region'] = 3
        if 'englishonly' in params:
            if params['englishonly']:
                params['englishonly'] = 1
            else:
                del params['englishonly']
        return params

    def clean(self, s):
        """clean the title name for search"""
        #return s
        return s.replace('.', ' ').replace('_', ' ').replace(',', '')\
                         .replace('-', ' ').strip().lower()

    @internet(log)
    def nzbid_from_search(self, url, name, query):
        """Parses nzb download url from api results"""
        import time
        import difflib
        matched_results = []
        log.debug("Sleeping to respect nzbmatrix rules about hammering the API")
        time.sleep(10)
        apireturn = self.parse_nzb_matrix_api(urlopener(url, log).read(),
                                              query)
        if not apireturn:
            return None
        else:
            names = []
            for result in apireturn:
                names.append(result["NZBNAME"])
            matches = difflib.get_close_matches(name, names, 1, 0.3)
            if len(matches) == 0:
                return None
            else:
                for result in apireturn:
                    if result["NZBNAME"] == matches[0]:
                        break
            for match in matches: # Already sorted
                for result in apireturn:
                    if result.get(match, False):
                        matched_results.append(result)
            return matched_results

    def parse_nzb_matrix_api(self, apireturn, title):
        import re
        apireturn = str(apireturn)
        if (apireturn == "error:nothing_found" or
            apireturn == "error:no_nzb_found"):
            log.debug("Nothing found from nzbmatrix for search on %s" % title)
            return []
        elif apireturn[:6] == 'error:':
            log.error("Error recieved from nzbmatrix API: %s" % apireturn[6:])
            return []
        results = []
        api_result = {}
        apire = re.compile(r"([A-Z_]+):(.+);$")
        for line in apireturn.splitlines():
            match = apire.match(line)
            if not match and line == "|" and api_result != {}:
                #not an empty api result
                results.append(api_result)
                api_result = dict()
            elif match:
                api_result[match.group(1)] = match.group(2)
            else:
                log.debug("Recieved non-matching line in nzbmatrix API search: "
                          "%s" % line)
        if api_result != {}:
            results.append(api_result)
        return results

register_plugin(NzbMatrix, 'nzbmatrix', groups=['search'])
