# Narrating equations and formulas

For math-heavy lessons (machine learning, linear algebra, calculus, statistics, probability).
The equation goes **on screen**; the narration explains it so a listener can follow it.
TTS can't read math notation: never put raw symbols (`σ`, `∑`, `x²`, `∂`, `θ̂`, `‖w‖`, `→`, `^T`)
in `voiceover` text. Write the spoken words yourself. Captions show what you wrote, so
spoken-form captions are expected and fine.

## Decide: read it, summarize it, or explain it

| Equation | Narration | Example |
|---|---|---|
| **Small**: ≤ ~6 symbols, one operation chain, the viewer will reuse it | Read it aloud exactly, then say what it means | "z equals x minus mu, over sigma. [pause] In words: how many standard deviations x is from the mean." |
| **Medium**: one idea, but several terms or a sum or integral | Give the meaning in a sentence; read only its key piece | "The loss averages the squared errors over all n examples." (show `L = 1/n ∑ (yᵢ − ŷᵢ)²`) |
| **Large**: derivations, matrix products with many factors, multi-line results | Don't read it. Build it up on screen term by term, narrating each term's role | "This first term rewards fitting the data. [pause] This second term penalizes large weights." |

Default to **meaning first**: say what the equation computes and why, in plain words, before or
instead of the symbols. Read a formula aloud only when the viewer gains from hearing its exact
shape (a definition they'll reuse, such as a z-score, a gradient step or Bayes' rule).
Never read an equation aloud *and* have the narration conflict with what's on screen.

Recipe for a key formula (one idea per voiceover block):
1. Purpose: "We want to compare a test value to the training data."
2. Show the equation; read it if it's small: "z equals x minus mu, all over sigma."
3. Meaning, using names rather than letters: "Subtract the training mean from the test value,
   then divide by the training standard deviation."
4. Worked numbers: "With a mean of fifty and a standard deviation of ten, a value of seventy
   gives a z of two."
5. Highlight the matching part of the equation on screen as each piece is spoken (bookmarks).

## Speaking conventions

Choose one spoken form per symbol and keep it for the whole lesson. Record your choices in
notes.md (under "Spoken math"). **Name symbols when they're introduced** ("sigma, the standard
deviation") and use the name afterward when that's clearer than the letter.

**Grouping is the hard part:** speech has no parentheses. Use "all over", "the quantity …",
"times the sum of …", or split the formula into two sentences. Keep the screen as the source of
truth for exact structure. Add `[pause]` between terms of a long expression, not inside one.

### Arithmetic and algebra
| Written | Say |
|---|---|
| `a/b`, fraction | "a over b"; numerator with several terms: "a plus b, all over c" |
| `x²`, `x³`, `xⁿ` | "x squared", "x cubed", "x to the n" |
| `√x`, `∛x` | "the square root of x", "the cube root of x" |
| `|x|` | "the absolute value of x" |
| `≈`, `≠`, `≤`, `≥`, `∝` | "is approximately", "is not equal to", "is at most", "is at least", "is proportional to" |
| `±` | "plus or minus" |
| `x₁`, `x_i`, `x_{ij}` | "x one", "x sub i", "x i j" (or "the i j entry of X") |
| `f(x)` | "f of x" |
| `exp(x)`, `eˣ`, `log x`, `ln x` | "e to the x", "log of x", "the natural log of x" |
| `n!` | "n factorial" |

### Linear algebra
| Written | Say |
|---|---|
| bold `x`, `w` (vectors) | "the vector x", "the weight vector w" (say "vector" the first time) |
| `A` (matrix) | "the matrix A" |
| `Aᵀ`, `A⁻¹` | "A transpose", "A inverse" |
| `Ax`, `AB` | "A times x", "A times B" (or "A applied to x") |
| `x · y`, `xᵀy` | "the dot product of x and y" |
| `‖x‖`, `‖x‖₂²` | "the norm of x", "the squared length of x" |
| `A ∈ ℝ^{m×n}` | "A is an m by n matrix of real numbers" |
| `det A`, `tr A` | "the determinant of A", "the trace of A" |
| `λ`, `Av = λv` | "lambda"; "A times v equals lambda times v" |
| `I`, `0` | "the identity matrix", "the zero vector" |

### Calculus
| Written | Say |
|---|---|
| `df/dx`, `f′(x)` | "the derivative of f with respect to x", "f prime of x" |
| `∂L/∂w` | "the partial derivative of L with respect to w" (later, briefly: "how L changes as w changes") |
| `∇L`, `∇_θ L` | "the gradient of L", "the gradient of L with respect to theta" |
| `∫_a^b f(x) dx` | "the integral of f of x from a to b" |
| `lim_{x→0}` | "the limit as x goes to zero" |
| `Δx` | "the change in x" |
| `θ ← θ − η∇L` | "update theta by subtracting the learning rate times the gradient" |

### Probability and statistics
| Written | Say |
|---|---|
| `μ`, `σ`, `σ²` | "mu", "sigma", "sigma squared"; name them: "the mean", "the standard deviation", "the variance" |
| `x̄`, `ŷ`, `θ̂` | "x bar" (the sample mean), "y hat" (the prediction), "theta hat" (the estimate) |
| `P(A)`, `P(A | B)` | "the probability of A", "the probability of A given B" |
| `E[X]`, `Var(X)` | "the expected value of X", "the variance of X" |
| `X ~ N(μ, σ²)` | "X follows a normal distribution with mean mu and variance sigma squared" |
| `∑_{i=1}^{n} xᵢ` | "the sum of x i, for i from one to n" (or just "add up all the x values") |
| `∏`, `argmax_θ` | "the product of …", "the value of theta that maximizes …" |
| `p(x; θ)` | "the probability of x under parameters theta" |

### Greek letters and ML notation
Say Greek letters by name: alpha, beta, gamma, delta, epsilon, eta, theta, lambda, mu, pi,
rho, sigma, tau, phi, chi, psi, omega. Common ML meanings to say in words at least once:
η "the learning rate", λ "the regularization strength", θ "the model parameters",
σ(·) "the sigmoid function" (say "sigmoid of z", not "sigma of z", to avoid confusing it with the
standard deviation), `softmax(z)` "the softmax of z", `ReLU(x)` "ReLU of x",
`ℒ`/`J` "the loss", `ε` "the noise" or "epsilon".

## TTS mechanics
- Put spoken words directly in the narration: `"z equals x minus mu, over sigma"`, not `"z = (x − μ)/σ"`.
  The number normalizer still turns digits into words ("2" → "two"), but it does **not** read symbols.
- Respell names that the voice garbles via lesson.yaml `pronounce:` (e.g. `{ReLU: "ray-loo",
  softmax: "soft max", argmax: "arg max", Adam: "Adam", logit: "lodge-it"}`), and keep
  normal spelling in visible text.
- Single letters can be swallowed or misread ("a", "I", "L"). Read the word first ("the vector a",
  "the matrix I") or add a respelling, and listen to every line that ends in a lone letter.
- Prefer "x sub i" over "x i" when "x i" could be heard as "xi". Prefer "y hat" to "y-hat".
- Use `[pause]` between the read-aloud formula and its meaning; use bookmarks to highlight each
  term on screen as it is spoken.

## On screen (no LaTeX)
Equations use `Text`/`MarkupText` with Unicode: `MarkupText('z = (x − μ) / σ')`,
`'x<sub>i</sub>'`, `'σ<sup>2</sup>'` (MarkupText supports `<sub>`/`<sup>`), `ŷ`, `θ̂`, `∑`,
`∂`, `∇`, `‖w‖`, `ℝ`. Use the `style.MONO` font only for code. Color-code symbols consistently
(e.g. the same color for μ in the formula, the narration highlight and the plot) and keep each
equation ≤ 1 line at font ≥ 30 where possible. Split long derivations into
one-step-per-beat transforms.

## Review checklist additions
- [ ] No raw math symbols in any `voiceover` text (`study review --lint` + a grep for `[=^²√∑∂∇σμθλ]`).
- [ ] Every symbol named at first use in speech; spoken forms consistent with notes.md "Spoken math".
- [ ] Small key formulas read aloud *and* restated in words; large ones explained term by term, not recited.
- [ ] Spoken grouping matches the on-screen structure ("all over" etc.); worked numbers agree with the screen.
- [ ] Listened to formula lines (lone letters, Greek names, "sub", "hat") or noted the limitation.
