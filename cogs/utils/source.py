import os
import inspect


def source(self, *, command: str):
    """Displays my full source code or for a specific command.

    To display the source code of a subcommand you can separate it by periods, e.g. tag.create for the create subcommand of the tag command or by spaces.

    Code taken from [Robodanny](https://github.com/Rapptz/RoboDanny).
    """
    source_url = 'https://github.com/WitherredAway/Yeet.'
    branch = 'master'
    if command is None:
        return source_url


    if command == 'help':
        src = type(self.bot.help_command)
        module = src.__module__
        filename = inspect.getsourcefile(src)
    else:
        obj = self.bot.get_command(command.replace('.', ' '))
        if obj is None:
            return 'Could not find command.'


        # since we found the command we're looking for, presumably anyway, let's
        # try to access the code itself
        src = obj.callback.__code__
        module = obj.callback.__module__
        filename = src.co_filename


    lines, firstlineno = inspect.getsourcelines(src)
    if not module.startswith('discord'):
        # not a built-in command
        location = os.path.relpath(filename).replace('\\', '/')
    else:
        location = module.replace('.', '/') + '.py'
        source_url = 'https://github.com/Rapptz/discord.py'
        branch = 'master'


    final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
    return final_url