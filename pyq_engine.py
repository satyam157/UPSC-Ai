from llm import ask_llm

def predict(news):
    text = "\n".join(news)

    return ask_llm("Based on current affairs, predict UPSC questions:\n" + text)