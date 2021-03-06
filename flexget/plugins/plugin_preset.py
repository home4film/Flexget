import logging
from flexget import validator
from flexget.manager import register_config_key
from flexget.plugin import priority, register_plugin, PluginError, register_parser_option, plugins as all_plugins

log = logging.getLogger('preset')


class PluginPreset(object):
    """
    Use presets.

    Example::

      preset: movies

    Example, list of presets::

      preset:
        - movies
        - imdb
    """

    def __init__(self):
        self.warned = False

    def validator(self):
        root = validator.factory()
        root.accept('text')
        root.accept('boolean')
        presets = root.accept('list')
        presets.accept('text')
        return root

    def prepare_config(self, config):
        if config is None or isinstance(config, bool):
            config = []
        elif isinstance(config, basestring):
            config = [config]
        return config

    @priority(255)
    def on_process_start(self, task, config):
        if config is False: # handles 'preset: no' form to turn off preset on this task
            return
        config = self.prepare_config(config)

        # add global in except when disabled with no_global
        if 'no_global' in config:
            config.remove('no_global')
            if 'global' in config:
                config.remove('global')
        elif not 'global' in config:
            config.append('global')

        toplevel_presets = task.manager.config.get('presets', {})

        # apply presets
        for preset in config:
            if preset not in toplevel_presets:
                if preset == 'global':
                    continue
                raise PluginError('Unable to find preset %s for task %s' % (preset, task.name), log)
            if toplevel_presets[preset] is None:
                log.warning('Preset `%s` is empty. Nothing to merge.' % preset)
                continue
            log.debug('Merging preset %s into task %s' % (preset, task.name))

            # We make a copy here because we need to remove
            preset_config = toplevel_presets[preset]
            # When there are presets within presets we remove the preset
            # key from the config and append it's items to our own
            if 'preset' in preset_config:
                nested_presets = self.prepare_config(preset_config['preset'])
                for nested_preset in nested_presets:
                    if nested_preset not in config:
                        config.append(nested_preset)
                    else:
                        log.warning('Presets contain each other in a loop.')
                # Replace preset_config with a copy without the preset key, to avoid merging errors
                preset_config = dict(preset_config)
                del preset_config['preset']

            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(preset_config, task.config)
            except MergeException, exc:
                raise PluginError('Failed to merge preset %s to task %s due to %s' % (preset, task.name, exc))

        log.trace('presets: %s' % config)

        # implements --preset NAME
        if task.manager.options.preset:
            if task.manager.options.preset not in config:
                task.enabled = False
                return


class DisablePlugin(object):
    """
    Allows disabling plugins when using presets.

    Example::

      presets:
        movies:
          download: ~/torrents/movies/
          .
          .

      tasks:
        nzbs:
          preset: movies
          disable_plugin:
            - download
          sabnzbd:
            .
            .

      #Task nzbs uses all other configuration from preset movies but removes the download plugin
    """

    def validator(self):
        root = validator.factory()
        root.accept('text')
        presets = root.accept('list')
        presets.accept('text')
        return root

    @priority(250)
    def on_task_start(self, task, config):
        if isinstance(config, basestring):
            config = [config]
        # let's disable them
        for disable in config:
            if disable in task.config:
                log.debug('disabling %s' % disable)
                del(task.config[disable])


def root_config_validator():
    """Returns a validator for the 'presets' key of config."""
    # TODO: better error messages
    valid_plugins = [p for p in all_plugins if hasattr(all_plugins[p].instance, 'validator')]
    root = validator.factory('dict')
    root.reject_keys(valid_plugins, message='plugins should go under a specific preset. '
        '(and presets are not allowed to be named the same as any plugins)')
    root.accept_any_key('dict').accept_any_key('any')
    return root


register_config_key('presets', root_config_validator)
register_plugin(PluginPreset, 'preset', builtin=True, api_ver=2)
register_plugin(DisablePlugin, 'disable_plugin', api_ver=2)

register_parser_option('--preset', action='store', dest='preset', default=False,
                       metavar='NAME', help='Execute tasks with given preset.')
