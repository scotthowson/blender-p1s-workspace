"""
TODO: disc cache mechanism. Either json or pickle
"""
import asyncio
from functools import partial, cache
from pathlib import Path
from csv import DictReader, DictWriter
import pickle
from typing import Generator, Dict, Any, Iterable, Tuple, List
from ast import literal_eval

from bpy.types import Context
from bpy.path import clean_name

from .toolz import dicttoolz, itertoolz, functoolz
from . import config

Preset = Dict[str, Any]
PresetCollection = Dict[str, Preset]
BpyEnum = List[Tuple[str, str, str, int]]
preset_categories_enum = []

_CSV_REQUIRED_FIELDS = {"preset_name", "thumb"}


def validate_csv(csv: Path) -> bool:
    """
    Validate csv, ensuring fieldnames and calculating thumbnail filenames
    Return False if missing preset_name field else True of validation
    """
    with open(csv, "r", newline="") as csv_file:
        reader = DictReader(csv_file)
        if reader.fieldnames is None:
            return False
        csv_fields = list(reader.fieldnames)
        missing_fields = list(_CSV_REQUIRED_FIELDS.difference(csv_fields))
        if "preset_name" in missing_fields:
            return False

        new_csv_fname = csv.with_suffix(".temp")
        with open(new_csv_fname, "w", newline="") as new_csv:
            csv_fields.extend(missing_fields)
            writer = DictWriter(new_csv, fieldnames=csv_fields)
            writer.writeheader()
            for entry in reader:
                entry["thumb"] = clean_name(entry["preset_name"])
                writer.writerow(entry)
    csv.unlink()
    new_csv_fname.rename(csv)
    return True


def find_preset_by_name(name: str, folder: Path) -> Preset:
    csv_files = folder.glob("*.csv")
    preset_collections = map(_read_general_preset_file, csv_files)
    for collection in preset_collections:
        if name in collection.keys():
            return collection[name]
    raise ValueError(f"No {name} preset in folder csv files")


def user_preset_type_categories(fastener_type: str) -> Iterable[Path]:
    """Return sorted list of directories in user_presets/{fastener_type}"""
    category_dir = config.USER_PRESETS_DIR / fastener_type
    category_dir.mkdir(exist_ok=True)  # Ensure root dir exists
    dirs = filter(lambda f: f.is_dir(), category_dir.iterdir())
    return sorted(list(dirs), key=lambda d: d.stem)


def user_preset_categories_enum(self, context: Context) -> BpyEnum:
    enum = []
    preset_dirs = user_preset_type_categories(self.fastener_type)

    for indx, preset in enumerate(preset_dirs):
        value = str.upper(preset.stem)
        label = str.title(preset.stem).replace("_", " ")
        description = str.upper(preset.stem)
        enum.append((value, label, description, indx))
    enum.sort(key=lambda i: i[1])

    # Move categories with 'Standard' prefix to end of enum
    for item in enum[:]:
        label: str = item[1]
        if label.startswith("Standard"):
            standard_item = enum.pop(enum.index(item))
            enum.append(standard_item)
            continue
        if label.startswith("Full"):
            standard_item = enum.pop(enum.index(item))
            enum.insert(0, standard_item)

    preset_categories_enum = enum
    return enum


def _csv_reader(csv_file: Path) -> Generator[Dict[str, str], None, None]:
    """Yield lines of file as dicts"""
    with open(csv_file, "r") as preset_file:
        reader = DictReader(preset_file)
        for entry in reader:
            yield entry


def _type_preset_line(entry: Dict[str, str]) -> Preset:
    """Apply correct types to preset values"""

    def _ensure_formatting(value):
        """Ensure correct case (title) for None and bool types"""
        if isinstance(value, list):
            value = value[0]
        if value.lower() in {"false", "true"}:
            return value.title()
        return value

    typed = {}
    formatted = {key: _ensure_formatting(value) for key, value in entry.items()}
    for key, value in formatted.items():
        try:
            evaled = literal_eval(value)
        except Exception as e:
            evaled = value
        typed.update({key: evaled})
    return typed


def _load_thread_definitions(csv_file: Path) -> Iterable[Preset]:
    def _reduce_to_fields(entry: Preset):
        return dicttoolz.keyfilter(lambda k: k in config.THREAD_FIELDS, entry)

    untyped_presets = _csv_reader(csv_file)
    typed_presets = map(_type_preset_line, untyped_presets)
    return map(_reduce_to_fields, typed_presets)


async def generate_thumbnails() -> Path:
    """Run an instance of Blender in an asyc subprocess and render preset thumbnails with it"""

    async def handle_request(reader, writer, queue: asyncio.Queue):
        data = await reader.read(100)
        message = data.decode()
        addr = writer.get_extra_info("peername")
        # print(f"Received {message} from {addr}")
        # print("Responding to Job Request")
        task = await queue.get()
        writer.write(task)
        await writer.drain()

        # print("Close the connection")
        writer.close()
        queue.task_done()

    async def run_renderer(print_log: bool = True):
        ip = config.THUMB_GEN_IP
        port = config.THUMB_GEN_PORT
        template = config.PRESET_THUMB_TEMPLATE
        script = config.PRESET_THUMB_SCRIPT

        script_args = ["--", ip, str(port)]
        args = ["-b", template, "-P", script] + script_args
        proc = await asyncio.create_subprocess_exec(
            config.BLENDER,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if print_log:
            if stdout:
                print(f"{stdout}\n{stdout.decode()}")
            if stderr:
                print(f"{stderr}\n{stderr.decode()}")

    async def main():
        job_queue = asyncio.Queue()
        resolution = int(config.PRESET_THUMB_RESOLUTION)
        output_dir = config.USER_PRESETS_DIR

        fastener_types = (
            "BOLT",
            "NUT",
            "SCREW",
            "THREADED_ROD",
        )
        for fastener_type in fastener_types:
            category_dirs = user_preset_type_categories(fastener_type)
            for category_dir in category_dirs:
                preset_csvs = list(category_dir.glob("*.csv"))
                valid_csvs = filter(validate_csv, preset_csvs)
                output_dir = category_dir
                preset_type = category_dir.stem
                for preset_csv in valid_csvs:
                    print(preset_csv)
                    presets = _read_general_preset_file(preset_csv)
                    job = (fastener_type, preset_type, presets, output_dir, resolution)

                    await job_queue.put(pickle.dumps(job))

        # Write termination command
        terminate = pickle.dumps("TERMINATE")
        await job_queue.put(terminate)

        server_callback = partial(handle_request, queue=job_queue)
        ip = config.THUMB_GEN_IP
        port = config.THUMB_GEN_PORT
        job_server = await asyncio.start_server(server_callback, ip, port)

        addrs = ", ".join(str(sock.getsockname()) for sock in job_server.sockets)
        print(f"Running job server on {addrs}")
        async with job_server:
            await job_server.start_serving()
            await run_renderer(config.DEBUG_PRINT_THUMB_RENDER_LOG)
            # await job_queue.join()

    # asyncio.run(main(), debug=True)
    print("Thumbnail rendering complete")
    await main()


def _read_general_preset_file(csv_file: Path) -> Dict[str, Preset]:
    """Read csv files and return as dict of 'preset_name': preset"""

    def _populate_thread_values(preset: Preset) -> Preset:
        """Populate thread fields from 'thread_preset' field value"""
        thread_name = preset.get("thread_preset")
        if thread_name is not None:
            thread_preset = thread_presets().get(thread_name)
            preset.update(thread_preset)
        return preset

    # Get presets
    untyped_presets = _csv_reader(csv_file)
    typed_presets = map(_type_preset_line, untyped_presets)
    typed_presets = map(_populate_thread_values, typed_presets)
    return {preset["preset_name"]: preset for preset in typed_presets}


def _load_fastener_presets(fastener_type: str):
    presets_by_category = {}
    category_dir = user_preset_type_categories(fastener_type)
    for category in category_dir:
        csv_files = category.glob("*.csv")
        preset_collections = map(_read_general_preset_file, csv_files)
        presets_by_category[category.stem] = dicttoolz.merge(preset_collections)
    return presets_by_category


# @cache
def bolt_presets():
    return _load_fastener_presets("BOLT")


# @cache
def nut_presets():
    return _load_fastener_presets("NUT")


# @cache
def screw_presets():
    return _load_fastener_presets("SCREW")


# @cache
def thread_rod_presets():
    return _load_fastener_presets("THREADED_ROD")


# @cache
def thread_presets() -> Dict[str, Preset]:
    csv_file = config.METRIC_THREADS_FILE
    presets = _load_thread_definitions(csv_file)
    return {preset["thread_name"]: preset for preset in presets}


_presets = {
    "BOLT": bolt_presets,
    "NUT": nut_presets,
    "SCREW": screw_presets,
    "THREADED_ROD": thread_rod_presets,
}


def get(key: str):
    return _presets.get(key)()


def clear_caches() -> None:
    # return None
    # print("Fastener cache cleared")
    caches = (bolt_presets, nut_presets, screw_presets, thread_presets)
    for func in caches:
        func.cache_clear()
