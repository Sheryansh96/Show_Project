"""infra_mapper — parses a CDK repo + service-package repo into an infra diagram.

Modules:
    constants   — ignore lists, resource-type tables, all compiled regexes
    text_utils  — brace/string-aware text scanning helpers shared by the parser
    cdk_parser  — regex-based extraction of CDK constructs and their edges
    enrichment  — resolves container/lambda code assets to human descriptions
    model       — assembles parsed constructs into the renderable tree
    render      — emits the self-contained HTML/CSS/JS diagram
    cli         — argument parsing and the `main()` entry point
"""
