"""File utilities — platform-hostile: hardcoded separators, missing encoding, /tmp paths."""
import os
import os.path


def find_python_files(root_dir):
    """Find all .py files under root_dir."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                # String concatenation instead of os.path.join or pathlib
                results.append(dirpath + "/" + filename)
    return results


def read_config(config_path):
    """Read a config file and return lines — no encoding specified."""
    f = open(config_path)
    lines = f.readlines()
    f.close()
    return [line.rstrip("\n") for line in lines]


def write_report(data, output_dir):
    """Write a report file to output_dir."""
    # Hardcoded separator — breaks on Windows
    output_path = output_dir + "/" + "report.txt"
    f = open(output_path, "w")
    for key, value in data.items():
        f.write(key + ": " + str(value) + "\n")
    f.close()
    return output_path


def get_cache_dir():
    """Return a cache directory path."""
    # Hardcoded Unix path — breaks on Windows
    home = os.environ.get("HOME", "/tmp")
    cache = home + "/.cache/myapp"
    if not os.path.exists(cache):
        os.makedirs(cache)
    return cache


def join_paths(*parts):
    """Join path components."""
    # Manual string join instead of os.path.join / pathlib
    result = parts[0]
    for part in parts[1:]:
        if not result.endswith("/"):
            result = result + "/"
        result = result + part
    return result


def get_extension(filepath):
    """Get the file extension."""
    # os.path usage — ruff PTH rules prefer pathlib
    return os.path.splitext(filepath)[1]


def file_size_kb(filepath):
    """Return file size in KB."""
    return os.path.getsize(filepath) / 1024
