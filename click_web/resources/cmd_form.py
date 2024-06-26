from html import escape

import click
from flask import abort, render_template

import click_web
from click_web.exceptions import CommandNotFound
from click_web.resources.input_fields import get_input_field


def get_form_for(command_path: str):
    try:
        ctx_and_commands = _get_commands_by_path(command_path)
    except CommandNotFound as err:
        return abort(404, str(err))

    levels = _generate_form_data(ctx_and_commands)
    return render_template("command_form.html.j2", levels=levels, command=levels[-1]["command"], command_path=command_path)


def _get_commands_by_path(command_path: str) -> list[tuple[click.Context, click.Command]]:
    """
    Take a (slash separated) string and generate (context, command) for each level.
    :param command_path: "some_group/a_command"
    :return: Return a list from root to leaf commands. each element is (Click.Context, Click.Command)
    """
    command_path_items = command_path.split("/")
    command_name, *command_path_items = command_path_items
    command = click_web.click_root_cmd
    if command.name != command_name:
        raise CommandNotFound(f"Failed to find root command {command_name}. There is a root command named:{command.name}")
    result = []
    with click.Context(command, info_name=command, parent=None) as ctx:
        result.append((ctx, command))
        # dig down the path parts to find the leaf command
        parent_command = command
        for command_name in command_path_items:
            command = parent_command.get_command(ctx, command_name)
            if command:
                # create sub context for command
                ctx = click.Context(command, info_name=command, parent=ctx)
                parent_command = command
            else:
                raise CommandNotFound(
                    'Failed to find command for path "{}". Command "{}" not found. Must be one of {}'.format(  # noqa: UP032
                        command_path, command_name, parent_command.list_commands(ctx)
                    )
                )
            result.append((ctx, command))
    return result


def _generate_form_data(ctx_and_commands: list[tuple[click.Context, click.Command]]):
    """
    Construct a list of contexts and commands generate a python data structure for rendering jinja form
    :return: a list of dicts
    """
    levels = []
    for command_index, (ctx, command) in enumerate(ctx_and_commands):
        # force help option off, no need in web.
        command.add_help_option = False
        command.html_help = _process_help(command.help)

        input_fields = [
            get_input_field(ctx, param, command_index, param_index) for param_index, param in enumerate(command.get_params(ctx))
        ]
        levels.append({"command": command, "fields": input_fields})

    return levels


def _process_help(help_text):
    """
    Convert click command help into html to be presented to browser.
    Respects the '\b' char used by click to mark pre-formatted blocks.
    Also escapes html reserved characters in the help text.

    :param help_text: str
    :return: A html formatted help string.
    """
    help_ = []
    in_pre = False
    html_help = ""
    if not help_text:
        return html_help

    line_iter = iter(help_text.splitlines())
    while True:
        try:
            line = next(line_iter)
            if in_pre and not line.strip():
                # end of code block
                in_pre = False
                html_help += "\n".join(help_)
                help_ = ["</pre>"]
                continue
            elif line.strip() == "\b":
                # start of code block
                in_pre = True
                html_help += "<br>\n".join(help_)
                help_ = ["<pre>"]
                continue
            help_.append(escape(line))
        except StopIteration:
            break

    html_help += "\n".join(help_) if in_pre else "<br>\n".join(help_)
    return html_help
