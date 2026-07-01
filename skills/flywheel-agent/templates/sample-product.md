# Sample Product Template

Use this template to create your product profile for Flywheel Agent.

## Product Information

**Product Name:** YourProduct
**URL:** https://yourproduct.com
**One-liner:** Brief description of what your product does

**Category:** Choose from:
- ai-productivity
- e-commerce intelligence
- developer-tools
- marketing-software
- finance-software
- healthcare-software
- e-commerce
- other

## ICP (Ideal Customer Profile)

**Buyer:** Primary decision maker (e.g., "founder", "CTO", "marketing manager")

**Company Stage:**
- pre-seed
- seed
- series-a
- series-b+
- enterprise

**Pain Points:** List 3-5 specific problems your product solves:
- Problem 1
- Problem 2
- Problem 3

**Keywords:** Relevant industry terms your ICP uses:
- keyword1
- keyword2
- keyword3

## Competitors

List 2-5 direct competitors with full URLs:
- https://competitor1.com
- https://competitor2.com
- https://competitor3.com

## Positioning

**Primary Claim:** What makes you different (e.g., "First AI-powered X for Y")

**Proof Points:** Evidence that supports your claim:
- Specific metric or improvement
- Unique feature or approach
- Customer validation

**Not Positioning:** What you're NOT:
- not a CRM
- not a generic tool
- not enterprise software

## Budget

**Weekly Budget:** $50-500 (how much to spend per week on customer acquisition)
**Max Single Spend:** $10-100 (largest single payment without special approval)

## Usage

Save this as `my-product.md` and run:
```bash
python flywheel_intake.py "$(cat my-product.md)"
```

Or run the explicit demo fixture:
```bash
python flywheel_intake.py --demo
```

Do not use the demo fixture for a real product sprint.