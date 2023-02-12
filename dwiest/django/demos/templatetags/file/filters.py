from django import template

register = template.Library()

@register.filter(name='format_bytes')
def format_bytes(size, precision):
  if isinstance(size,int) == False:
    return size

  # 2**10 = 1024
  power = 2**10
  n = 0
  power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
  while size > power:
    size /= power
    n += 1
  size = round(size, precision)
  return "{} {}B".format(size, power_labels[n])
