import re
from flexget.plugin import priority, register_plugin


class AddTrackers(object):

    """
        Adds tracker URL to torrent files.

        Configuration example:

        add_trackers:
          - uri://tracker_address:port/

        This will add all tracker URL uri://tracker_address:port/.
        TIP: You can use global section in configuration to make this enabled on all tasks.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('url', protocols=['udp', 'http'])
        return trackers

    @priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                for url in config:
                    if not url in entry['torrent'].get_multitrackers():
                        entry['torrent'].add_multitracker(url)
                        self.log.info('Added %s tracker to %s' % (url, entry['title']))
            if entry['url'].startswith('magnet:'):
                entry['url'] += ''.join(['&tr=' + url for url in config])


class RemoveTrackers(object):

    """
        Removes trackers from torrent files using regexp matching.

        Configuration example:

        remove_trackers:
          - moviex

        This will remove all trackers that contain text moviex in their url.
        TIP: You can use global section in configuration to make this enabled on all tasks.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('regexp')
        return trackers

    @priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                trackers = entry['torrent'].get_multitrackers()
                for tracker in trackers:
                    for regexp in config or []:
                        if re.search(regexp, tracker, re.IGNORECASE | re.UNICODE):
                            self.log.debug('remove_trackers removing %s because of %s' % (tracker, regexp))
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            self.log.info('Removed %s' % tracker)
            if entry['url'].startswith('magnet:'):
                for regexp in config:
                    # Replace any tracker strings that match the regexp with nothing
                    tr_search = r'&tr=([^&]*%s[^&]*)' % regexp
                    entry['url'] = re.sub(tr_search, '', entry['url'], re.IGNORECASE | re.UNICODE)

class ModifyTrackers(object):

    """
        Modify trackers in torrent files to use http protocol.

        Configuration example:

        modify_trackers: true

        This will convert all trackers that are udp URIs into their http equivalent.
        If the http equivalent is already registered the entry is removed.
        TIP: You can use global section in configuration to make this enabled on all tasks.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    """
        Made lower priority than other tracker operations so it is executed afterwards.
    """
    @priority(126)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                trackers = entry['torrent'].get_multitrackers()
                for tracker in trackers:
                    if tracker.startswith('udp://'):
                        entry['torrent'].remove_multitracker(tracker)
                        self.log.info('Removed %s tracker from %s' % (tracker, entry['title']))
                        
                        replacement = 'http' + tracker[3:]
                        
                        if not replacement in entry['torrent'].get_multitrackers():                            
                            entry['torrent'].add_multitracker(replacement)
                            self.log.info('Added %s tracker to %s' % (replacement, entry['title']))

            if entry['url'].startswith('magnet:'):
                # Replace any tracker strings that use udp trackers with the http equivalent
                tr_search = r'&tr=udp'
                entry['url'] = re.sub(tr_search, '&tr=http', entry['url'], re.IGNORECASE | re.UNICODE)
                 
register_plugin(AddTrackers, 'add_trackers', api_ver=2)
register_plugin(RemoveTrackers, 'remove_trackers', api_ver=2)
register_plugin(ModifyTrackers, 'modify_trackers', api_ver=2)
