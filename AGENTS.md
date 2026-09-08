# Repository Agent Rules

- Never fabricate UE registration, PDU session, packet capture, traffic, recovery, timing, or Linux runtime success.
- Static validation, fixture validation, and real runtime validation must remain separate claims.
- Sample logs under `logs/` are not real runtime evidence.
- Do not add LLM, RAG, chatbot, vector database, or AI-agent features to this repository.
- Do not make RF claims; UERANSIM is not an RF simulator.
- Fault injection must be restricted to lab containers, lab configs, and scoped Docker networks.
- A healthy baseline must pass before fault scenarios are interpreted.
- Every fault path must include rollback or clearly report cleanup failure.
- Real evidence must include environment, version, commit, scenario, and capability metadata.
- Do not commit private subscriber material, production credentials, tokens, huge logs, or unsanitized pcaps.
