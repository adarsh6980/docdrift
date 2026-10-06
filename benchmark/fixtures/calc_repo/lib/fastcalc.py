# v2.0: add_numbers was renamed to add, default precision changed
def add(a, b): return a + b
def mean(xs, precision=2): return round(sum(xs) / len(xs), precision)
