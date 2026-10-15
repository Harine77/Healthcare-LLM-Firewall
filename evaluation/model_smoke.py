from app.model_client import generate_answer

if __name__ == "__main__":
    answer = generate_answer(
        query="What are some general benefits of drinking enough water?",
        contexts=[],
    )
    print("Real model inference: PASS")
    print("Response preview:")
    print(answer[:600])
