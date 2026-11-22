import requests
import re
import json
import datetime
import ast


class JobStats:
    def __init__(
        self,
        job_id,
        spider,
        start_time,
        end_time,
        scraped_count,
        dropped_count,
        warning_count,
        error_count,
        max_mem,
        status,
    ):
        self.job_id = job_id
        self.spider = spider
        self.start_time = start_time
        self.end_time = end_time
        self.scraped_count = scraped_count
        self.dropped_count = dropped_count
        self.warning_count = warning_count
        self.error_count = error_count
        self.max_mem = max_mem
        self.status = status

    @staticmethod
    def create_from_logfile(job_id, spider, start_time, end_time, log_content):

        result_dict = JobStats.parse_stats_dump(log_content)
        # If there is no stats dump, the job was interrupted. Skip it.
        if result_dict is None:
            return None

        scraped_count = (
            result_dict["item_scraped_count"]
            if "item_scraped_count" in result_dict
            else 0
        )
        dropped_count = (
            result_dict["item_dropped_count"]
            if "item_dropped_count" in result_dict
            else 0
        )
        warning_count = (
            result_dict["log_count/WARNING"]
            if "log_count/WARNING" in result_dict
            else 0
        )
        error_count = (
            result_dict["log_count/ERROR"] if "log_count/ERROR" in result_dict else 0
        )
        max_mem = result_dict.get("memusage/max")
        status = result_dict.get("finish_reason")

        return JobStats(
            job_id,
            spider,
            start_time,
            end_time,
            scraped_count,
            dropped_count,
            warning_count,
            error_count,
            max_mem,
            status,
        )

    @staticmethod
    def parse_stats_dump(log_content):
        # Scrapy writes the stats dump with pprint after the
        # [scrapy.statscollectors] line: the first line starts with "{" and
        # every following line of the dump is indented. The dump is parsed,
        # never evaluated: only literals and datetime.datetime(...) calls with
        # literal arguments are converted, and a value of any other kind is
        # left out of the dict. Return None when the log has no dump, or when
        # the dump is not a dict literal.
        match = re.search(
            r"\[scrapy\.statscollectors\][^\n]*\n(\{[^\n]*(?:\n [^\n]*)*)",
            log_content,
        )
        if not match:
            return None
        try:
            tree = ast.parse(match.group(1), mode="eval")
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            # MemoryError: the parser stack overflows on deeply nested input.
            return None
        if not isinstance(tree.body, ast.Dict):
            return None

        result_dict = {}
        for key_node, value_node in zip(tree.body.keys, tree.body.values):
            try:
                key = JobStats._convert_node(key_node)
                value = JobStats._convert_node(value_node)
            except (ValueError, TypeError, OverflowError):
                continue
            if isinstance(key, str):
                result_dict[key] = value
        return result_dict

    @staticmethod
    def _convert_node(node):
        # Convert a literal or datetime.datetime(...) node to its value. Raise
        # ValueError for any other kind of node.
        if node is None:
            # The key of a "**mapping" entry in a dict literal.
            raise ValueError("Unsupported stats value")
        if isinstance(node, ast.Call) and JobStats._is_name(
            node.func, "datetime", "datetime"
        ):
            args = [JobStats._convert_node(arg) for arg in node.args]
            kwargs = {}
            for keyword in node.keywords:
                if keyword.arg == "tzinfo":
                    if not JobStats._is_name(
                        keyword.value, "datetime", "timezone", "utc"
                    ):
                        raise ValueError("Unsupported stats value")
                    kwargs["tzinfo"] = datetime.timezone.utc
                elif keyword.arg is not None:
                    kwargs[keyword.arg] = JobStats._convert_node(keyword.value)
                else:
                    # A "**mapping" argument.
                    raise ValueError("Unsupported stats value")
            numbers = args + [v for k, v in kwargs.items() if k != "tzinfo"]
            if not all(type(number) is int for number in numbers):
                raise ValueError("Unsupported stats value")
            return datetime.datetime(*args, **kwargs)
        if isinstance(node, ast.List):
            return [JobStats._convert_node(element) for element in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(JobStats._convert_node(element) for element in node.elts)
        if isinstance(node, ast.Dict):
            return {
                JobStats._convert_node(key): JobStats._convert_node(value)
                for key, value in zip(node.keys, node.values)
            }
        # Strings, numbers, booleans, None, sets and signed numbers.
        return ast.literal_eval(node)

    @staticmethod
    def _is_name(node, *parts):
        # Return whether the node is the dotted name given by the parts.
        for part in reversed(parts[1:]):
            if not isinstance(node, ast.Attribute) or node.attr != part:
                return False
            node = node.value
        return isinstance(node, ast.Name) and node.id == parts[0]

    def __str__(self):
        return f"Job ID: {self.job_id}, Spider: {self.spider}, Start Time: {self.start_time}, End Time: {self.end_time}"
