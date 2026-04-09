def evaluate(user, correct):
    total = len(correct)
    attempted = len(user)
    correct_n = sum([1 for u,c in zip(user,correct) if u==c])
    wrong = attempted - correct_n
    acc = (correct_n/attempted*100) if attempted else 0
    marks = correct_n*2 - wrong*0.66

    return total, attempted, correct_n, wrong, round(acc,2), round(marks,2)