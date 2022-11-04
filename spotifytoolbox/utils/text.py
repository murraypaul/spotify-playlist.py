def remove_punctuation(text):
    if "." in text:
        text = text.replace("."," ")
    return text

def remove_featuring(text):
    if "(feat" in text:
        text = text.partition("(feat")[0]
    if "(Feat" in text:
        text = text.partition("(Feat")[0]
    return text

def remove_brackets(text):
    if "(" in text:
        text = text.partition("(")[0]
    return text

def name_matches(left,right):
    left = left.lower()
    right = right.lower()
    left = left.replace('&','and')
    right = right.replace('&','and')
    left = left.replace(':',' ')
    right = right.replace(':',' ')
    left = left.replace('-',' ')
    right = right.replace('-',' ')
    left = left.replace('  ',' ')
    right = right.replace('  ',' ')

    #    print("Comparing '%s' with '%s'" % (left, right))
    return left == right


