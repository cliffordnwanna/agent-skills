"""Offline candidate generation and human-review export for the FastAPI corpus."""

# ruff: noqa: E501

import csv
import hashlib
import json
import re
from pathlib import Path

from rag_eval_kit.models import CorpusDocument, EvaluationCase, QuestionCategory


def _case(
    category: QuestionCategory,
    number: int,
    question: str,
    answer: str,
    evidence: tuple[tuple[str, str], ...] = (),
    *,
    unanswerable: bool = False,
) -> EvaluationCase:
    return EvaluationCase(
        question_id=f"{category}-{number:02}",
        question=question,
        reference_answer=answer,
        reference_evidence=[text for _, text in evidence],
        expected_source_ids=list(dict.fromkeys(source_id for source_id, _ in evidence)),
        category=category,
        unanswerable=unanswerable,
    )


_CANDIDATE_DATA: tuple[tuple, ...] = (
    # Direct questions
    (
        "direct",
        "Where does data in a request body come from?",
        "It is data the client sends to the API.",
        (("body", "body is data sent by the client to your API."),),
    ),
    (
        "direct",
        "What does a response body contain?",
        "It contains data the API sends back to the client.",
        (("body", "body is the data your API sends to the client."),),
    ),
    (
        "direct",
        "What kind of model is used to declare a request body?",
        "A Pydantic BaseModel can be used to declare it.",
        (
            (
                "body",
                "you use [Pydantic](https://pydantic.dev/docs/) models with all their power and benefits.",
            ),
        ),
    ),
    (
        "direct",
        "How does FastAPI treat a Pydantic model attribute with a default value?",
        "The attribute is not required; `None` can make it optional.",
        (
            (
                "body",
                "The same as when declaring query parameters, when a model attribute has a default value, it is not required. Otherwise, it is required. Use `None` to make it just optional.",
            ),
        ),
    ),
    (
        "direct",
        "Which HTTP methods are listed for sending data in a request body?",
        "POST, PUT, DELETE, or PATCH.",
        (
            (
                "body",
                "To send data, you should use one of: `POST` (the most common), `PUT`, `DELETE` or `PATCH`.",
            ),
        ),
    ),
    (
        "direct",
        "How does FastAPI interpret a non-path function parameter by default?",
        "It is interpreted as a query parameter.",
        (
            (
                "query-params",
                'When you declare other function parameters that are not part of the path parameters, they are automatically interpreted as "query" parameters.',
            ),
        ),
    ),
    (
        "direct",
        "Where are query parameters written in a URL?",
        "After `?`, with multiple key-value pairs separated by `&`.",
        (
            (
                "query-params",
                "The query is the set of key-value pairs that go after the `?` in a URL, separated by `&` characters.",
            ),
        ),
    ),
    (
        "direct",
        "What Python value does a path parameter annotated as `int` receive for `/items/3`?",
        'It receives the integer 3, not the string `"3"`.',
        (
            (
                "path-params",
                'Notice that the value your function received (and returned) is `3`, as a Python `int`, not a string `"3"`.',
            ),
        ),
    ),
    (
        "direct",
        "What does a response model do to returned fields?",
        "It limits and filters output to fields declared by the response type.",
        (
            (
                "response-model",
                "* It will **limit and filter** the output data to what is defined in the return type.",
            ),
        ),
    ),
    (
        "direct",
        "Which extra package is required for FastAPI form support?",
        "`python-multipart`.",
        (
            (
                "request-forms",
                "To use forms, first install [`python-multipart`](https://github.com/Kludex/python-multipart).",
            ),
        ),
    ),
    (
        "direct",
        "How are underscores handled in declared header parameter names by default?",
        "FastAPI converts underscores to hyphens when extracting and documenting headers.",
        (
            (
                "header-params",
                "So, by default, `Header` will convert the parameter names characters from underscore (`_`) to hyphen (`-`) to extract and document the headers.",
            ),
        ),
    ),
    (
        "direct",
        "How does FastAPI represent duplicate values for a header declared as a list?",
        "The values are received as a Python list.",
        (("header-params", "all the values from the duplicate header as a Python `list`."),),
    ),
    # Paraphrased questions
    (
        "paraphrased",
        "If a client submits a JSON object, what can FastAPI use to define its shape?",
        "A Pydantic model can define the request body's structure.",
        (
            (
                "body",
                "you use [Pydantic](https://pydantic.dev/docs/) models with all their power and benefits.",
            ),
        ),
    ),
    (
        "paraphrased",
        "What happens when a submitted body contains a value of the wrong type?",
        "FastAPI converts and validates the data, returning an error that identifies where and what was incorrect.",
        (
            (
                "body",
                "If the data is invalid, it will return a nice and clear error, indicating exactly where and what was the incorrect data.",
            ),
        ),
    ),
    (
        "paraphrased",
        "How can a developer make a non-path query argument optional?",
        "Give it a default such as `None`; without a default, it is required.",
        (
            (
                "query-params",
                "If you don't want to add a specific value but just make it optional, set the default as `None`.",
            ),
        ),
    ),
    (
        "paraphrased",
        "Does a typed query parameter remain a raw string after parsing?",
        "No. FastAPI converts it to the declared Python type and validates it.",
        (
            (
                "query-params",
                "But when you declare them with Python types (in the example above, as `int`), they are converted to that type and validated against it.",
            ),
        ),
    ),
    (
        "paraphrased",
        "What will an integer path argument receive when the URL contains `/items/3`?",
        "The value is converted to the Python integer 3.",
        (
            (
                "path-params",
                'Notice that the value your function received (and returned) is `3`, as a Python `int`, not a string `"3"`.',
            ),
        ),
    ),
    (
        "paraphrased",
        "Why should an endpoint that returns sensitive data declare an output model?",
        "A response model filters fields, which can prevent undeclared data from being returned.",
        (
            (
                "response-model",
                "* It will **limit and filter** the output data to what is defined in the return type.",
            ),
        ),
    ),
    (
        "paraphrased",
        "What happens if an API handler returns data missing a required response field?",
        "FastAPI treats that as an application error and returns a server error rather than invalid output.",
        (
            (
                "response-model",
                "If the data is invalid (e.g. you are missing a field), it means that *your* app code is broken, not returning what it should, and it will return a server error instead of returning incorrect data.",
            ),
        ),
    ),
    (
        "paraphrased",
        "What encoding is normally used when a browser submits ordinary form fields?",
        "`application/x-www-form-urlencoded`.",
        (
            (
                "request-forms",
                'normally encoded using the "media type" `application/x-www-form-urlencoded`.',
            ),
        ),
    ),
    (
        "paraphrased",
        "How does the request encoding change when a form carries files?",
        "It uses `multipart/form-data`.",
        (
            (
                "request-forms",
                "But when the form includes files, it is encoded as `multipart/form-data`.",
            ),
        ),
    ),
    (
        "paraphrased",
        "Can an HTTP header name differ in capitalization and still be recognized?",
        "Yes. HTTP header names are case-insensitive.",
        (("header-params", "HTTP headers are case-insensitive"),),
    ),
    (
        "paraphrased",
        "What does a response type annotation provide besides JSON serialization?",
        "FastAPI validates the returned data and documents its response schema in OpenAPI.",
        (
            ("response-model", "FastAPI will use this return type to:"),
            ("response-model", "* **Validate** the returned data."),
        ),
    ),
    (
        "paraphrased",
        "What should be used to explicitly declare a function argument as form data?",
        "Use `Form`; without it, parameters may be treated as query or JSON body parameters.",
        (("request-forms", "Use `Form` to declare form data input parameters."),),
    ),
    # Questions that require two source documents
    (
        "multi_document",
        "In a handler with a path ID, a Pydantic item, and a separate simple string argument, where does each value come from?",
        "The ID comes from the path, the Pydantic model from the request body, and the remaining simple parameter is a query parameter.",
        (
            ("body", "taken from the path**"),
            ("body", "taken from the request body**"),
            ("query-params", 'automatically interpreted as "query" parameters.'),
        ),
    ),
    (
        "multi_document",
        "How do FastAPI's request-side Pydantic model and response model serve different purposes?",
        "The request model describes and validates incoming body data; the response model validates and filters outgoing data.",
        (
            (
                "body",
                "you use [Pydantic](https://pydantic.dev/docs/) models with all their power and benefits.",
            ),
            (
                "response-model",
                "* It will **limit and filter** the output data to what is defined in the return type.",
            ),
        ),
    ),
    (
        "multi_document",
        "How are a typed path parameter and a typed query parameter handled?",
        "Both are parsed and validated according to their Python type annotations.",
        (
            (
                "path-params",
                "You can declare the type of a path parameter in the function, using standard Python type annotations:",
            ),
            (
                "query-params",
                "But when you declare them with Python types (in the example above, as `int`), they are converted to that type and validated against it.",
            ),
        ),
    ),
    (
        "multi_document",
        "How can an API accept form credentials while keeping undeclared fields out of its response?",
        "Declare incoming form fields with `Form`, and use an output response model that filters returned fields.",
        (
            (
                "request-forms",
                "With `Form` you can declare the same configurations as with `Body` (and `Query`, `Path`, `Cookie`), including validation, examples, an alias (e.g. `user-name` instead of `username`), etc.",
            ),
            (
                "response-model",
                "* It will **limit and filter** the output data to what is defined in the return type.",
            ),
        ),
    ),
    (
        "multi_document",
        "If `item_id` is in the route and `q` is a simple string defaulting to `None`, which are path versus query values?",
        "`item_id` is taken from the path; `q` is a query parameter and is optional because it has a `None` default.",
        (
            ("body", "it will be used as a path parameter."),
            ("query-params", "the function parameter `q` will be optional"),
        ),
    ),
    (
        "multi_document",
        "How do request-body models and response return types both contribute to API documentation?",
        "Their JSON Schemas are included in the generated OpenAPI schema and shown in the automatic docs.",
        (
            (
                "body",
                "Those schemas will be part of the generated OpenAPI schema, and used by the automatic documentation",
            ),
            (
                "response-model",
                "* Add a **JSON Schema** for the response, in the OpenAPI *path operation*.",
            ),
        ),
    ),
    (
        "multi_document",
        "What is the safe way to handle a password sent in an input model before returning the user object?",
        "Use an output model that omits the password; FastAPI filters fields to the declared response model.",
        (
            (
                "response-model",
                "We can instead create an input model with the plaintext password and an output model without it:",
            ),
            (
                "response-model",
                "So, **FastAPI** will take care of filtering out all the data that is not declared in the output model (using Pydantic).",
            ),
        ),
    ),
    (
        "multi_document",
        "When a route takes a path value and a structured JSON payload, how does FastAPI distinguish them?",
        "It takes the matching route parameter from the path and the Pydantic model parameter from the body.",
        (
            ("body", "taken from the path**"),
            ("body", "taken from the request body**"),
            (
                "path-params",
                "The value of the path parameter `item_id` will be passed to your function as the argument `item_id`. ",
            ),
        ),
    ),
    (
        "multi_document",
        "How does FastAPI handle the type of a URL query value compared with the type declared in a path operation?",
        "Query values arrive as strings but are converted and validated when typed; path parameters can likewise be declared with Python types and parsed.",
        (
            ("query-params", 'As they are part of the URL, they are "naturally" strings.'),
            (
                "path-params",
                "You can declare the type of a path parameter in the function, using standard Python type annotations:",
            ),
        ),
    ),
    (
        "multi_document",
        "What should a developer use for OAuth-style username/password inputs, and what should control which fields are returned?",
        "Use form fields with `Form` and define an output response model that filters fields.",
        (
            ("request-forms", "it is required to send a `username` and `password` as form fields."),
            (
                "response-model",
                "**limit and filter** the output data to what is defined in the return type.",
            ),
        ),
    ),
    (
        "multi_document",
        "How can an app validate an input object's fields and then document its response contract?",
        "Use a Pydantic model for the request body and a response type/model for output validation and OpenAPI documentation.",
        (
            ("body", "Read the body of the request as JSON."),
            ("body", "Validate the data."),
            ("response-model", "Add a **JSON Schema** for the response"),
        ),
    ),
    (
        "multi_document",
        "How do default values affect requiredness for a Pydantic body field versus a query parameter?",
        "A body model attribute with a default is not required, and a query parameter with a default is also not required.",
        (
            ("body", "when a model attribute has a default value, it is not required."),
            (
                "query-params",
                "When you declare a default value for non-path parameters (for now, we have only seen query parameters), then it is not required.",
            ),
        ),
    ),
    # Difficult retrieval questions: conditions, exceptions, and similar distractors
    (
        "difficult_retrieval",
        "Is a GET request body forbidden by FastAPI, and will it appear in Swagger UI?",
        "FastAPI supports GET bodies for very complex or extreme use cases, but behavior is undefined by specifications and discouraged; Swagger UI will not show the body documentation and proxies may not support it.",
        (
            (
                "body",
                "Sending a body with a `GET` request has an undefined behavior in the specifications, nevertheless, it is supported by FastAPI, only for very complex/extreme use cases.",
            ),
            (
                "body",
                "As it is discouraged, the interactive docs with Swagger UI won't show the documentation for the body when using `GET`, and proxies in the middle might not support it.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "What happens to a boolean query parameter if it is omitted, set to `no`, or set to `maybe`?",
        "Omission uses the default (False in the example); `no` converts to False; `maybe` produces a 422 validation error.",
        (
            ("query-params", "including case variations) are converted to"),
            ("query-params", "produces a `422` validation error."),
        ),
    ),
    (
        "difficult_retrieval",
        "Which route should be declared first when both `/users/me` and `/users/{user_id}` exist?",
        "Declare `/users/me` first because path operations are evaluated in order.",
        (
            (
                "path-params",
                "Because *path operations* are evaluated in order, you need to make sure that the path for `/users/me` is declared before the one for `/users/{user_id}`:",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "If both a function return annotation and `response_model` are declared, which one determines the response schema?",
        "`response_model` takes priority.",
        (("response-model", "will take priority and be used by FastAPI."),),
    ),
    (
        "difficult_retrieval",
        "Can a developer combine JSON `Body` fields and `Form` fields in one request body?",
        "No. Form requests use form encoding rather than `application/json`, so JSON Body fields cannot be combined as expected.",
        (
            (
                "request-forms",
                "You can declare multiple `Form` parameters in a *path operation*, but you can't also declare `Body` fields that you expect to receive as JSON, as the request will have the body encoded using `application/x-www-form-urlencoded` instead of `application/json`.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "Why can reusing an input model that contains a password as a response model expose the password?",
        "If that model is used by another operation, the password can be sent to every client; use an output model without it.",
        (
            (
                "response-model",
                "But if we use the same model for another *path operation*, we could be sending our user's passwords to every client.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "What compatibility risk is mentioned when disabling underscore-to-hyphen conversion for headers?",
        "Some proxies and servers disallow headers containing underscores.",
        (
            (
                "header-params",
                "Before setting `convert_underscores` to `False`, bear in mind that some HTTP proxies and servers disallow the usage of headers with underscores.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "What does a missing required query argument do, and how can it be made optional instead?",
        "Without a default it is required; set a default such as `None` to make it optional.",
        (
            (
                "query-params",
                "make a query parameter required, you can just not declare any default value:",
            ),
            ("query-params", "make it optional, set the default as `None`."),
        ),
    ),
    (
        "difficult_retrieval",
        "If a query boolean is empty or contains an unrecognized word, does FastAPI silently treat it as False?",
        "No. An empty value or an unrecognized value such as `maybe` produces a 422 validation error.",
        (("query-params", "produces a `422` validation error."),),
    ),
    (
        "difficult_retrieval",
        "Does a response model only add documentation, or can it change the actual returned data?",
        "It also converts and filters output to the declared response type.",
        (
            (
                "response-model",
                "FastAPI will use this `response_model` to do all the data documentation, validation, etc. and also to **convert and filter the output data** to its type declaration.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "For a form with a file, should the request use URL-encoded fields or multipart encoding?",
        "Use `multipart/form-data` when the form includes files.",
        (
            (
                "request-forms",
                "But when the form includes files, it is encoded as `multipart/form-data`.",
            ),
        ),
    ),
    (
        "difficult_retrieval",
        "When a path parameter is typed as an integer, is `4.2` accepted as an integer?",
        "No. The docs state that an error appears for `4.2` when the path parameter is declared as `int`.",
        (
            (
                "path-params",
                "The same error would appear if you provided a `float` instead of an `int`, as in: [http://127.0.0.1:8000/items/4.2](http://127.0.0.1:8000/items/4.2)",
            ),
        ),
    ),
    # Unanswerable questions intentionally have no supporting evidence.
    *[
        (
            "unanswerable",
            question,
            "The supplied FastAPI documentation subset does not specify this.",
            (),
            True,
        )
        for question in (
            "What is FastAPI's default PostgreSQL connection-pool size?",
            "How many requests per second does FastAPI guarantee on a four-core server?",
            "Which cloud provider hosts the official FastAPI production API?",
            "What is the monthly price of a commercial FastAPI support plan?",
            "Does FastAPI store uploaded files in a database by default?",
            "What is the maximum WebSocket message size enforced by FastAPI?",
            "Which embedding model does FastAPI use for semantic search?",
            "How long does FastAPI retain application logs by default?",
            "What encryption algorithm does FastAPI use for database passwords?",
            "How many worker processes should every FastAPI deployment use?",
            "What is FastAPI's built-in vector database retention policy?",
            "Does FastAPI guarantee zero downtime during every deployment?",
        )
    ],
)


def build_candidates() -> list[EvaluationCase]:
    candidates: list[EvaluationCase] = []
    counts: dict[str, int] = {}
    for row in _CANDIDATE_DATA:
        category, question, answer, evidence, *optional = row
        unanswerable = bool(optional and optional[0])
        counts[category] = counts.get(category, 0) + 1
        candidates.append(
            _case(
                category,
                counts[category],
                question,
                answer,
                evidence,
                unanswerable=unanswerable,
            )
        )
    expected = {
        "direct": 12,
        "paraphrased": 12,
        "multi_document": 12,
        "difficult_retrieval": 12,
        "unanswerable": 12,
    }
    if counts != expected:
        raise ValueError(f"Candidate distribution mismatch: {counts}")
    return candidates


def validate_candidates(candidates: list[EvaluationCase], corpus: list[CorpusDocument]) -> None:
    sources = {document.source_id: document.content for document in corpus}
    ids = [candidate.question_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate question IDs must be unique")
    questions = [re.sub(r"\W+", " ", c.question.casefold()).strip() for c in candidates]
    if len(questions) != len(set(questions)):
        raise ValueError("Candidate questions must be unique")
    for candidate in candidates:
        if candidate.unanswerable:
            if candidate.expected_source_ids or candidate.reference_evidence:
                raise ValueError(f"Unanswerable case has evidence: {candidate.question_id}")
            continue
        if not candidate.expected_source_ids or not candidate.reference_evidence:
            raise ValueError(f"Answerable case is missing evidence: {candidate.question_id}")
        if not set(candidate.expected_source_ids) <= sources.keys():
            raise ValueError(f"Unknown source ID: {candidate.question_id}")
        for evidence in candidate.reference_evidence:
            if not any(
                evidence in sources[source_id] for source_id in candidate.expected_source_ids
            ):
                raise ValueError(f"Evidence span is absent from corpus: {candidate.question_id}")


def write_candidate_files(
    candidates: list[EvaluationCase], output_dir: Path, *, overwrite: bool = False
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "candidate_questions.jsonl"
    csv_path = output_dir / "review.csv"
    mode = "w" if overwrite else "x"
    jsonl_content = "".join(candidate.model_dump_json() + "\n" for candidate in candidates)
    with jsonl_path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(jsonl_content)
    try:
        with csv_path.open(mode, encoding="utf-8", newline="") as handle:
            fields = [
                "question_id",
                "category",
                "question",
                "reference_answer",
                "reference_evidence_json",
                "expected_source_ids_json",
                "unanswerable",
                "keep",
                "reviewer",
                "review_notes",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for candidate in candidates:
                writer.writerow(
                    {
                        "question_id": candidate.question_id,
                        "category": candidate.category,
                        "question": candidate.question,
                        "reference_answer": candidate.reference_answer,
                        "reference_evidence_json": json.dumps(candidate.reference_evidence),
                        "expected_source_ids_json": json.dumps(candidate.expected_source_ids),
                        "unanswerable": str(candidate.unanswerable).lower(),
                        "keep": "",
                        "reviewer": "",
                        "review_notes": "",
                    }
                )
    except OSError:
        jsonl_path.unlink(missing_ok=True)
        raise
    return {
        "candidate_questions_sha256": hashlib.sha256(jsonl_content.encode("utf-8")).hexdigest(),
        "question_count": str(len(candidates)),
    }
