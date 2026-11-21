"""Three authored spike examples, not an approved benchmark or golden dataset."""

EXAMPLES = [
    {
        "id": "returns-supported",
        "input": "How long is the return window?",
        "actual_output": "Unused items may be returned within 30 days.",
        "expected_output": "Unused items may be returned within 30 days.",
        "retrieval_context": ["Unused items may be returned within 30 days."],
    },
    {
        "id": "shipping-contradiction",
        "input": "How much does standard shipping cost?",
        "actual_output": "Standard shipping is free.",
        "expected_output": "Standard shipping costs $5.",
        "retrieval_context": ["Standard shipping costs $5. Express shipping costs $15."],
    },
    {
        "id": "hours-distractor",
        "input": "When is customer support available?",
        "actual_output": "Support is available Monday to Friday, 9am to 5pm UTC.",
        "expected_output": "Monday to Friday, 9am to 5pm UTC.",
        "retrieval_context": [
            "Our fictional store sells notebooks.",
            "Support is available Monday to Friday, 9am to 5pm UTC.",
        ],
    },
]
