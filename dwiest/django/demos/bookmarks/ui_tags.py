"""Safe tag palette tokens stored in the existing style field."""
PALETTE = (('', 'Automatic'), ('ui:0', 'Amber'), ('ui:1', 'Blue'), ('ui:2', 'Teal'), ('ui:3', 'Purple'), ('ui:4', 'Rose'), ('ui:5', 'Green'))


def tag_tone(tag):
    if tag.style in {value for value, _ in PALETTE if value}:
        return tag.style[-1]
    value = 0
    for char in tag.title.lower():
        value = (value * 31 + ord(char)) & 0xffffffff
    return str(value % 6)
