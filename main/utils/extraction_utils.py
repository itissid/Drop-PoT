def flatten_list(lst):
    result = []
    for item in lst or []:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result
