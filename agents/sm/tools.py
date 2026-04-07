from smolagents import tool

__all__ = ["read_file", "update_content", "remove_file"]


@tool
def read_file(file: str) -> str:
    """
    Open a UTF-8 encoded text file and return its contents.

    This function reads the file located at the given path and returns
    the entire content as a single string.

    Args:
        file (str): Path to the file to be opened and read.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        UnicodeDecodeError: If the file cannot be decoded using UTF-8 encoding.
        OSError: If an I/O error occurs while opening or reading the file.
    """
    import builtins
    with builtins.open(file, encoding="utf-8") as f:
        return f.read()


@tool
def update_content(filepath: str, content: str) -> None:
    """
    Write text content to a file.

    This function writes the given content to the file at the specified
    path using UTF-8 encoding. If the file already exists, it will be
    overwritten. If it does not exist, a new file will be created.

    Args:
        filepath (str): Path to the file to be written.
        content (str): Text content to write into the file.

    Returns:
        None

    Raises:
        OSError: If an I/O error occurs while writing to the file.
    """
    import builtins
    with builtins.open(filepath, 'w', encoding="utf-8") as f:
        f.write(content)


@tool
def remove_file(filepath: str) -> None:
    """
    Remove a file at the specified path.

    This function attempts to delete the file located at ``filepath``.
    If the deletion fails, the error is caught and printed.

    Args:
        filepath (str): The path to the file to be removed.

    Returns:
        None

    Raises:
        None: All exceptions are caught internally and reported via printing.
    """
    import os
    try:
        os.unlink(filepath)
    except Exception as e:
        print("Cannot delete the file due to the following error:", e)
