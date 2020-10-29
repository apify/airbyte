"""
MIT License

Copyright (c) 2020 Airbyte

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import importlib
import os.path
import sys
import tempfile

from airbyte_protocol import AirbyteMessage, Status, Type

from .integration import ConfigContainer, Source
from .logger import AirbyteLogger

impl_module = os.environ.get("AIRBYTE_IMPL_MODULE", Source.__module__)
impl_class = os.environ.get("AIRBYTE_IMPL_PATH", Source.__name__)
module = importlib.import_module(impl_module)
impl = getattr(module, impl_class)

logger = AirbyteLogger()


class AirbyteEntrypoint(object):
    def __init__(self, source):
        self.source = source

    def start(self, args):
        # set up parent parsers
        parent_parser = argparse.ArgumentParser(add_help=False)
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(title="commands", dest="command")

        # spec
        subparsers.add_parser("spec", help="outputs the json configuration specification", parents=[parent_parser])

        # check
        check_parser = subparsers.add_parser("check", help="checks the config can be used to connect", parents=[parent_parser])
        required_check_parser = check_parser.add_argument_group("required named arguments")
        required_check_parser.add_argument("--config", type=str, required=True, help="path to the json configuration file")

        # discover
        discover_parser = subparsers.add_parser(
            "discover", help="outputs a catalog describing the source's schema", parents=[parent_parser]
        )
        required_discover_parser = discover_parser.add_argument_group("required named arguments")
        required_discover_parser.add_argument("--config", type=str, required=True, help="path to the json configuration file")

        # read
        read_parser = subparsers.add_parser("read", help="reads the source and outputs messages to STDOUT", parents=[parent_parser])

        read_parser.add_argument("--state", type=str, required=False, help="path to the json-encoded state file")
        required_read_parser = read_parser.add_argument_group("required named arguments")
        required_read_parser.add_argument("--config", type=str, required=True, help="path to the json configuration file")
        required_read_parser.add_argument(
            "--catalog", type=str, required=True, help="path to the catalog used to determine which data to read"
        )

        # parse the args
        parsed_args = main_parser.parse_args(args)

        # execute
        cmd = parsed_args.command
        if not cmd:
            raise Exception("No command passed")

        # todo: add try catch for exceptions with different exit codes

        with tempfile.TemporaryDirectory() as temp_dir:
            if cmd == "spec":
                message = AirbyteMessage(type=Type.SPEC, spec=self.source.spec(logger))
                print(message.json(exclude_unset=True))
                sys.exit(0)

            raw_config = self.source.read_config(parsed_args.config)

            rendered_config_path = os.path.join(temp_dir, "config.json")
            rendered_config = self.source.transform_config(raw_config)
            self.source.write_config(rendered_config, rendered_config_path)

            config_container = ConfigContainer(
                raw_config=raw_config,
                rendered_config=rendered_config,
                raw_config_path=parsed_args.config,
                rendered_config_path=rendered_config_path,
            )

            if cmd == "check":
                check_result = self.source.check(logger, config_container)

                if check_result.status == Status.SUCCEEDED:
                    logger.info("Check succeeded")
                else:
                    logger.error("Check failed")

                output_message = AirbyteMessage(type=Type.CONNECTION_STATUS, connectionStatus=check_result).json(exclude_unset=True)
                print(output_message)
                sys.exit(0)
            elif cmd == "discover":
                catalog = self.source.discover(logger, config_container)
                print(AirbyteMessage(type=Type.CATALOG, catalog=catalog).json(exclude_unset=True))
                sys.exit(0)
            elif cmd == "read":
                generator = self.source.read(logger, config_container, parsed_args.catalog, parsed_args.state)
                for message in generator:
                    print(message.json(exclude_unset=True))
                sys.exit(0)
            else:
                raise Exception("Unexpected command " + cmd)


def launch(source, args):
    AirbyteEntrypoint(source).start(args)


def main():
    # set up and run entrypoint
    source = impl()

    if not isinstance(source, Source):
        raise Exception("Source implementation provided does not implement Source class!")

    launch(source, sys.argv[1:])
