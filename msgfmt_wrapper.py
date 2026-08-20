"""Small, dependency-free replacement for GNU msgfmt used by the SCons build."""

import ast
import struct
import sys


def _parse_po(path):
    messages = {}
    msgctxt = None
    msgid = None
    msgid_plural = None
    msgstr = {}
    section = None
    fuzzy = False

    def commit():
        nonlocal msgctxt, msgid, msgid_plural, msgstr, fuzzy
        if msgid is not None and not fuzzy:
            key = msgid
            if msgctxt is not None:
                key = f"{msgctxt}\x04{key}"
            if msgid_plural is not None:
                key = f"{key}\0{msgid_plural}"
            if msgstr:
                messages[key] = "\0".join(msgstr[index] for index in sorted(msgstr))
        msgctxt = None
        msgid = None
        msgid_plural = None
        msgstr = {}
        fuzzy = False

    with open(path, encoding="utf-8-sig") as po_file:
        for line_number, raw_line in enumerate(po_file, 1):
            line = raw_line.strip()
            if not line:
                commit()
                section = None
                continue
            if line.startswith("#"):
                if line.startswith("#,") and any(
                    flag.strip() == "fuzzy" for flag in line[2:].split(",")
                ):
                    fuzzy = True
                continue
            if line.startswith("msgctxt "):
                section = ("msgctxt", None)
                msgctxt = ast.literal_eval(line[8:])
            elif line.startswith("msgid_plural "):
                section = ("msgid_plural", None)
                msgid_plural = ast.literal_eval(line[13:])
            elif line.startswith("msgid "):
                if msgid is not None:
                    commit()
                section = ("msgid", None)
                msgid = ast.literal_eval(line[6:])
            elif line.startswith("msgstr["):
                bracket = line.index("]")
                index = int(line[7:bracket])
                section = ("msgstr", index)
                msgstr[index] = ast.literal_eval(line[bracket + 1:].strip())
            elif line.startswith("msgstr "):
                section = ("msgstr", 0)
                msgstr[0] = ast.literal_eval(line[7:])
            elif line.startswith('"'):
                value = ast.literal_eval(line)
                if section is None:
                    raise ValueError(f"{path}:{line_number}: orphaned string")
                name, index = section
                if name == "msgctxt":
                    msgctxt += value
                elif name == "msgid":
                    msgid += value
                elif name == "msgid_plural":
                    msgid_plural += value
                else:
                    msgstr[index] += value
            else:
                raise ValueError(f"{path}:{line_number}: unsupported PO syntax: {line}")
    commit()
    return messages


def _write_mo(messages, path):
    encoded = sorted(
        (msgid.encode("utf-8"), msgstr.encode("utf-8"))
        for msgid, msgstr in messages.items()
    )
    count = len(encoded)
    key_table_offset = 7 * 4
    value_table_offset = key_table_offset + count * 8
    key_data_offset = value_table_offset + count * 8
    key_data = b""
    key_table = []
    for key, _value in encoded:
        key_table.append((len(key), key_data_offset + len(key_data)))
        key_data += key + b"\0"
    value_data_offset = key_data_offset + len(key_data)
    value_data = b""
    value_table = []
    for _key, value in encoded:
        value_table.append((len(value), value_data_offset + len(value_data)))
        value_data += value + b"\0"

    with open(path, "wb") as mo_file:
        mo_file.write(struct.pack(
            "<7I", 0x950412DE, 0, count, key_table_offset,
            value_table_offset, 0, 0,
        ))
        for entry in key_table:
            mo_file.write(struct.pack("<2I", *entry))
        for entry in value_table:
            mo_file.write(struct.pack("<2I", *entry))
        mo_file.write(key_data)
        mo_file.write(value_data)


def main(args):
    output = None
    source = None
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "-o" and index + 1 < len(args):
            output = args[index + 1]
            index += 2
        elif argument.endswith(".po"):
            source = argument
            index += 1
        else:
            index += 1
    if output is None or source is None:
        raise SystemExit(f"Invalid msgfmt arguments: {args!r}")
    _write_mo(_parse_po(source), output)
    print(f"Compiled {source} -> {output}")


if __name__ == "__main__":
    main(sys.argv[1:])
