from pipelines.qa import build_pipeline
from dotenv import load_dotenv

load_dotenv()

def run_multi_source(question: str) -> str:
    """Run the end-to-end multi-source QA pipeline (param extract + parallel fetch)."""
    chain = build_pipeline()
    return chain.invoke({"question": question})


if __name__ == "__main__":
    q1 = ("Give daily prices for Tomato in Pune market, Pune district, Maharashtra (limit 20)")

    q2 = ("Give daily prices for Tomato in Pune market, Pune district, Maharashtra (limit 20).")

    q3 = ("Show variety-wise prices for Onion in Nagpur, Maharashtra on 15/03/2018.")

    print("\n--- Multi-source answer ---\n", run_multi_source(q1))