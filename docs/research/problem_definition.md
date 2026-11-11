# Problem definition

## Context

Climate-finance information is fragmented across publishers (multilateral funds, development
banks, research datasets) with different formats, identifiers, definitions of "climate" and
amount types. Organizations working on Pakistan's climate needs — and elsewhere — struggle to
see what has been financed, by whom, for what purpose, and where evidence is strong or weak.

## Users

Analysts and programme staff at funders, NGOs, government units and researchers who need to
discover, screen, compare and prioritize climate-related projects for **human review**.

## Product goals (MVP)

1. Discover real historical and current climate-finance projects.
2. Search by country (Pakistan default), sector, year and climate purpose.
3. Screen project descriptions for climate relevance with a trained model.
4. Show available financial amounts and the evidence behind each classification.
5. Compare projects; prioritize uncertain or relevant projects for review.
6. Explore allocation scenarios under transparent, user-set budget constraints.
7. View actual funding trends and historical project information.

## Research foundation

*A Benchmark Dataset of Chinese Development Finance with Climate Relevance and SDG Annotations
from 2000–2021* (Scientific Data, 2026) supplies human climate-relevance annotations, which make
supervised learning possible.

## Initial ML research question

> **"Can a supervised model recognize climate-relevant development-finance projects from their
> textual descriptions, and how reliably can it apply this learning to unseen projects and
> Pakistan-related records?"**

This is a **text-classification and generalization** question. It does **not** ask whether a
project will be funded, succeed, or produce environmental benefit.

## Why decision support, not autonomous approval

- The model learns *how annotators labelled descriptions*, not real-world outcomes.
- Training labels come mainly from one financier population (Chinese development finance);
  transfer to other sources and to Pakistan is an open empirical question.
- Source records may be incomplete, outdated or duplicated across publishers.
- Funding decisions involve policy, due diligence and local context outside any dataset.
- Errors have real consequences; accountability must stay with people.

Therefore Compassio surfaces evidence, uncertainty and transparent scenarios, and leaves
decisions to human reviewers.

## Out of scope

Predicting funding success, environmental impact, financial return, or whether a project is
currently accepting funding.
