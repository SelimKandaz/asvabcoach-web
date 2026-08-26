from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from random import Random
from typing import Iterable

from app.services.question_profile_service import derive_question_profile


@dataclass(slots=True)
class GeneratedQuestionDraft:
    section: str
    skill_tag: str
    concept_tag: str
    template_family: str
    variant_signature: str
    reasoning_steps: int
    formula_stack: list[str] | None
    concept_stack: list[str] | None
    trap_type: str | None
    difficulty_level: int
    question_text: str
    choices: dict[str, str]
    correct_answer: str
    base_explanation: str
    wrong_a_explanation: str
    wrong_b_explanation: str
    wrong_c_explanation: str
    wrong_d_explanation: str
    quick_method: str
    complexity_score: int
    observed_correct_rate: float
    average_response_time_seconds: float
    has_figure: bool = False
    requires_figure: bool = False
    figure_type: str | None = None
    figure_data: dict | None = None
    figure_svg: str | None = None
    figure_alt_text: str | None = None
    figure_quality_status: str | None = None
    license_status: str | None = None
    source_profile: str | None = None


def _seed(*parts: object) -> int:
    blob = "::".join(str(part) for part in parts)
    return int(sha1(blob.encode("utf-8")).hexdigest()[:16], 16)


def _rng(*parts: object) -> Random:
    return Random(_seed(*parts))


def _format_number(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(round(float(value))))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _shuffle_choices(correct_text: str, distractors: Iterable[str], rng: Random) -> tuple[dict[str, str], str]:
    options = [correct_text, *distractors]
    unique: list[str] = []
    for option in options:
        if option not in unique:
            unique.append(option)
    while len(unique) < 4:
        unique.append(f"Choice {_format_number(len(unique) + 1)}")
    rng.shuffle(unique)
    labels = ["A", "B", "C", "D"]
    choices = {labels[index]: unique[index] for index in range(4)}
    correct_answer = next(label for label, value in choices.items() if value == correct_text)
    return choices, correct_answer


def _numeric_distractors(correct_value: float, rng: Random, *, spread: float = 4.0, precision: int = 0) -> list[str]:
    candidates: list[float] = []
    while len(candidates) < 3:
        delta = round(rng.uniform(0.75, spread), precision + 1)
        sign = -1 if len(candidates) % 2 else 1
        candidate = round(correct_value + (sign * delta), precision)
        if candidate <= 0:
            candidate = round(correct_value + abs(delta), precision)
        if candidate not in candidates and candidate != correct_value:
            candidates.append(candidate)
    return [_format_number(value) if precision == 0 else f"{value:.{precision}f}" for value in candidates]


def _base_quality(difficulty_level: int) -> tuple[int, float, float]:
    complexity_score = max(18, min(90, 18 + difficulty_level * 14))
    observed_correct_rate = round(max(0.28, min(0.95, 0.96 - (difficulty_level - 1) * 0.14)), 2)
    response_time = round(18.0 + difficulty_level * 7.5, 1)
    return complexity_score, observed_correct_rate, response_time


def _finalize_draft(
    *,
    section: str,
    skill_tag: str,
    difficulty_level: int,
    question_text: str,
    choices: dict[str, str],
    correct_answer: str,
    base_explanation: str,
    wrong_explanations: dict[str, str],
    quick_method: str,
    has_figure: bool = False,
    figure_type: str | None = None,
    figure_data: dict | None = None,
    figure_svg: str | None = None,
    figure_alt_text: str | None = None,
) -> GeneratedQuestionDraft:
    profile = derive_question_profile(
        section=section,
        skill_tag=skill_tag,
        question_text=question_text,
        has_figure=has_figure,
        figure_type=figure_type,
        figure_svg=figure_svg,
        generation_method="template",
        source_name="deterministic_generator",
        copyright_status="original",
    )
    resolved_difficulty = profile.recommended_difficulty_level
    complexity_score, observed_correct_rate, response_time = _base_quality(resolved_difficulty)
    return GeneratedQuestionDraft(
        section=section,
        skill_tag=skill_tag,
        concept_tag=profile.concept_tag,
        template_family=profile.template_family,
        variant_signature=profile.variant_signature,
        reasoning_steps=profile.reasoning_steps,
        formula_stack=profile.formula_stack,
        concept_stack=profile.concept_stack,
        trap_type=profile.trap_type,
        difficulty_level=resolved_difficulty,
        question_text=question_text,
        choices=choices,
        correct_answer=correct_answer,
        has_figure=has_figure,
        requires_figure=profile.requires_figure,
        figure_type=figure_type,
        figure_data=figure_data,
        figure_svg=figure_svg,
        figure_alt_text=figure_alt_text,
        figure_quality_status=profile.figure_quality_status,
        base_explanation=base_explanation,
        wrong_a_explanation=wrong_explanations["A"],
        wrong_b_explanation=wrong_explanations["B"],
        wrong_c_explanation=wrong_explanations["C"],
        wrong_d_explanation=wrong_explanations["D"],
        quick_method=quick_method,
        license_status=profile.license_status,
        source_profile=profile.source_profile,
        complexity_score=max(complexity_score, profile.derived_complexity_score),
        observed_correct_rate=observed_correct_rate,
        average_response_time_seconds=response_time,
    )


def _mcq(
    *,
    section: str,
    skill_tag: str,
    difficulty_level: int,
    question_text: str,
    correct_text: str,
    distractors: list[str],
    base_explanation: str,
    quick_method: str,
    wrong_reason: str,
) -> GeneratedQuestionDraft:
    rng = _rng(section, skill_tag, difficulty_level, question_text)
    choices, correct_answer = _shuffle_choices(correct_text, distractors, rng)
    wrong_explanations = {
        "A": wrong_reason,
        "B": wrong_reason,
        "C": wrong_reason,
        "D": wrong_reason,
    }
    wrong_explanations[correct_answer] = base_explanation
    return _finalize_draft(
        section=section,
        skill_tag=skill_tag,
        difficulty_level=difficulty_level,
        question_text=question_text,
        choices=choices,
        correct_answer=correct_answer,
        base_explanation=base_explanation,
        wrong_explanations=wrong_explanations,
        quick_method=quick_method,
    )


def _ar_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("AR", difficulty_level, index)
    template = index % 4
    if template == 0:
        start = rng.randint(20, 90)
        percent = rng.choice([10, 15, 20, 25, 30])
        correct = round(start * (1 + percent / 100.0))
        return _mcq(
            section="AR",
            skill_tag="percent_change",
            difficulty_level=difficulty_level,
            question_text=f"A price of ${start} increases by {percent}%. What is the new price?",
            correct_text=f"${_format_number(correct)}",
            distractors=[f"${_format_number(start + percent)}", f"${_format_number(correct - percent)}", f"${_format_number(correct + percent)}"],
            base_explanation=f"Increase the original price by {percent}% of ${start}. The new price is ${_format_number(correct)}.",
            quick_method="Multiply by 1 plus the percent.",
            wrong_reason="This choice comes from a common percentage slip or using the wrong base amount.",
        )
    if template == 1:
        rate = rng.randint(30, 75)
        time = rng.randint(2, 6)
        correct = rate * time
        return _mcq(
            section="AR",
            skill_tag="rate_time_distance",
            difficulty_level=difficulty_level,
            question_text=f"A truck travels at {rate} miles per hour for {time} hours. How far does it travel?",
            correct_text=f"{correct} miles",
            distractors=[f"{correct + rate} miles", f"{correct - rate} miles", f"{correct // 2} miles"],
            base_explanation=f"Use distance = rate × time, so {rate} × {time} = {correct} miles.",
            quick_method="Distance = rate times time.",
            wrong_reason="This answer uses the wrong operation or misses one of the factors.",
        )
    if template == 2:
        first = rng.randint(8, 24)
        second = rng.randint(8, 24)
        correct = round((first + second) / 2)
        return _mcq(
            section="AR",
            skill_tag="average_value",
            difficulty_level=difficulty_level,
            question_text=f"The scores {first} and {second} are averaged. What is the mean score?",
            correct_text=f"{correct}",
            distractors=[f"{first + second}", f"{abs(first - second)}", f"{correct + 3}"],
            base_explanation=f"Add the two scores and divide by 2: ({first} + {second}) / 2 = {correct}.",
            quick_method="Average = sum divided by count.",
            wrong_reason="This choice ignores the division by the number of values or uses the difference instead.",
        )
    numerator = rng.randint(1, 9)
    denominator = rng.randint(numerator + 1, 12)
    whole = rng.randint(2, 6)
    correct = round(whole * numerator / denominator, 2)
    distractors = _numeric_distractors(correct, rng, spread=2.5, precision=2)
    return _mcq(
        section="AR",
        skill_tag="fraction_part",
        difficulty_level=difficulty_level,
        question_text=(
            f"What is {numerator}/{denominator} of {whole}?"
        ),
        correct_text=f"{correct:.2f}",
        distractors=distractors,
        base_explanation=f"Multiply the whole number by the fraction: {whole} × {numerator}/{denominator} = {correct:.2f}.",
        quick_method="Multiply the whole by the fraction.",
        wrong_reason="This answer uses the wrong part of the fraction or the wrong operation.",
    )


def _mk_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("MK", difficulty_level, index)
    template = index % 4
    if template == 0:
        a = rng.randint(2, 9)
        x = rng.randint(3, 12)
        b = rng.randint(1, 8)
        c = a * x + b
        return _mcq(
            section="MK",
            skill_tag="linear_equation",
            difficulty_level=difficulty_level,
            question_text=f"Solve for x: {a}x + {b} = {c}.",
            correct_text=f"{x}",
            distractors=[f"{x + 1}", f"{x - 1}", f"{x + 2}"],
            base_explanation=f"Subtract {b}, then divide by {a}: x = ({c} - {b}) / {a} = {x}.",
            quick_method="Isolate x by reversing the operations.",
            wrong_reason="This option comes from a subtraction or division mistake.",
        )
    if template == 1:
        base = rng.randint(2, 6)
        power = rng.randint(2, 4)
        correct = base**power
        return _mcq(
            section="MK",
            skill_tag="exponents",
            difficulty_level=difficulty_level,
            question_text=f"What is {base}^{power}?",
            correct_text=f"{correct}",
            distractors=[f"{base * power}", f"{correct + base}", f"{correct - base}"],
            base_explanation=f"Exponentiation means repeated multiplication: {base}^{power} = {correct}.",
            quick_method="Read the exponent as repeated multiplication.",
            wrong_reason="This answer confuses multiplication with exponentiation.",
        )
    if template == 2:
        width = rng.randint(3, 9)
        length = rng.randint(width + 1, width + 8)
        correct = 2 * (length + width)
        return _mcq(
            section="MK",
            skill_tag="perimeter",
            difficulty_level=difficulty_level,
            question_text=f"A rectangle has a length of {length} and a width of {width}. What is its perimeter?",
            correct_text=f"{correct}",
            distractors=[f"{length * width}", f"{length + width}", f"{correct + 4}"],
            base_explanation=f"Perimeter = 2(length + width) = 2({length} + {width}) = {correct}.",
            quick_method="Double the sum of length and width.",
            wrong_reason="This choice uses area or forgets to double the sum.",
        )
    addend1 = rng.randint(1, 8)
    addend2 = rng.randint(1, 8)
    addend3 = rng.randint(1, 8)
    correct = addend1 + addend2 + addend3
    return _mcq(
        section="MK",
        skill_tag="order_of_operations",
        difficulty_level=difficulty_level,
        question_text=f"What is {addend1} + {addend2} × {addend3}?",
        correct_text=f"{addend1 + addend2 * addend3}",
        distractors=[f"{correct}", f"{(addend1 + addend2) * addend3}", f"{addend1 * addend2 + addend3}"],
        base_explanation=f"Multiply first: {addend2} × {addend3} = {addend2 * addend3}, then add {addend1} for a total of {addend1 + addend2 * addend3}.",
        quick_method="Multiply before you add.",
        wrong_reason="This answer adds too early or applies multiplication to the wrong pair.",
    )


WK_BANK: list[tuple[str, str, list[str]]] = [
    ("precise", "exact", ["vague", "timid", "hollow"]),
    ("scarce", "rare", ["noisy", "soft", "early"]),
    ("assist", "help", ["delay", "scatter", "hide"]),
    ("rapid", "fast", ["quiet", "heavy", "narrow"]),
    ("ancient", "old", ["modern", "brief", "solid"]),
    ("fragile", "delicate", ["stubborn", "costly", "remote"]),
    ("generous", "giving", ["careless", "restless", "frozen"]),
    ("obvious", "clear", ["distant", "crooked", "private"]),
    ("diligent", "hardworking", ["careless", "silent", "greedy"]),
    ("expand", "grow", ["refuse", "shrink", "borrow"]),
    ("permit", "allow", ["forbid", "wander", "repair"]),
    ("brief", "short", ["costly", "wooden", "humid"]),
    ("maintain", "keep", ["spoil", "borrow", "shake"]),
    ("cautious", "careful", ["reckless", "joyful", "dusty"]),
    ("resist", "withstand", ["invite", "scatter", "polish"]),
    ("urgent", "pressing", ["distant", "optional", "fragile"]),
    ("observe", "notice", ["ignore", "purchase", "divide"]),
    ("modify", "change", ["repeat", "settle", "rest"]),
    ("secure", "safe", ["uneven", "swift", "nervous"]),
    ("vivid", "bright", ["silent", "dull", "gentle"]),
    ("reliable", "dependable", ["unclear", "fragile", "empty"]),
    ("conclude", "finish", ["argue", "divide", "wander"]),
    ("abundant", "plentiful", ["scarce", "rigid", "hidden"]),
    ("initial", "first", ["final", "thick", "broken"]),
    ("reluctant", "unwilling", ["eager", "tidy", "polite"]),
    ("essential", "necessary", ["optional", "ancient", "fuzzy"]),
    ("deliberate", "careful", ["accidental", "rapid", "vacant"]),
    ("temporary", "short-term", ["permanent", "formal", "silent"]),
    ("decline", "decrease", ["expand", "borrow", "accept"]),
    ("sustain", "support", ["remove", "drown", "freeze"]),
]


PC_BANK: list[dict[str, object]] = [
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A bus depot changed its schedule so mechanics inspected vehicles before the morning rush instead of after lunch. Breakdowns dropped during commuter hours, and riders arrived on time more often.",
        "question": "Why did the depot change the inspection schedule?",
        "correct": "To reduce breakdowns during busy travel hours",
        "distractors": ["To hire more drivers", "To shorten the routes", "To raise ticket prices"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A school library moved its most requested science books to shelves near the front desk. Students found them faster, and checkout lines became shorter during study hall.",
        "question": "What was the main result of moving the books?",
        "correct": "Students found popular books more quickly",
        "distractors": ["The library bought fewer books", "The front desk closed earlier", "Science classes became longer"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "After several small spills, a warehouse painted yellow paths on the floor to separate forklifts from foot traffic. Near-miss incidents dropped during the next month.",
        "question": "Why were yellow paths painted on the floor?",
        "correct": "To separate vehicles from pedestrians",
        "distractors": ["To mark broken shelves", "To increase storage space", "To show where packages were sold"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A farm switched from watering fields at noon to watering them before sunrise. The soil stayed moist longer, and the farm used less water each week.",
        "question": "What can be inferred about early watering?",
        "correct": "Less water is lost to daytime heat",
        "distractors": ["Plants need no sunlight", "The farm expanded its fields", "The soil became harder to plow"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A city crew repaired cracked sidewalks near a senior center after staff reported several tripping hazards. Visitors said the route felt safer after the work was completed.",
        "question": "Why did the city crew repair the sidewalks?",
        "correct": "To remove a safety hazard",
        "distractors": ["To widen the parking lot", "To create a bike lane", "To lower the speed limit"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "During a heat wave, a delivery company loaded frozen goods last so they spent less time sitting in warm trucks. Fewer orders arrived damaged that week.",
        "question": "What was the purpose of loading frozen goods last?",
        "correct": "To keep them cold for more of the trip",
        "distractors": ["To make trucks heavier", "To shorten the delivery route", "To reduce the number of drivers"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A repair shop placed a checklist beside each service bay. Technicians missed fewer steps, and customers returned less often with the same problem.",
        "question": "What does the checklist mainly help technicians do?",
        "correct": "Complete each repair step consistently",
        "distractors": ["Order new tools", "Increase labor charges", "Store customer keys"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A hiking trail added numbered signs at each fork. Rangers found that lost hikers could describe their location more accurately when calling for help.",
        "question": "Why were the numbered signs useful?",
        "correct": "They helped hikers report where they were",
        "distractors": ["They made the trail shorter", "They increased parking capacity", "They warned about weather only"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A bakery began mixing dough in smaller batches throughout the morning instead of all at once at dawn. Bread sold later in the day stayed fresher on the shelves.",
        "question": "What problem did smaller batches solve?",
        "correct": "Bread was becoming stale before it sold",
        "distractors": ["The ovens were too large", "Customers wanted fewer choices", "The bakery lacked enough workers"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "When a clinic noticed long waits after lunch, it moved paperwork for returning patients online. The waiting room cleared faster by the end of the week.",
        "question": "What was the likely reason waits became shorter?",
        "correct": "Returning patients spent less time filling out forms on site",
        "distractors": ["The clinic treated fewer patients", "Doctors shortened every exam", "Lunch breaks were canceled"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A marina installed brighter lights at the fuel dock after sunset accidents were reported. Boat owners said docking became easier in the evening.",
        "question": "Why did the marina install brighter lights?",
        "correct": "To improve visibility and safety at night",
        "distractors": ["To attract more fish", "To reduce fuel prices", "To make docks longer"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A community center started sending text reminders one day before classes. Attendance improved even though class times did not change.",
        "question": "What best explains the attendance improvement?",
        "correct": "More people remembered to come to class",
        "distractors": ["Classrooms became larger", "Fees were increased", "The classes became shorter"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A factory stored frequently used bolts in bins beside each assembly station instead of in one central room. Workers spent less time walking away from their tables.",
        "question": "What was the main benefit of moving the bolt bins?",
        "correct": "Workers lost less time retrieving parts",
        "distractors": ["The bolts became cheaper", "The tables were moved outdoors", "Supervisors reduced inspections"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A school cafeteria offered sliced fruit near the checkout counter instead of on a side cart. More students chose fruit with lunch after the change.",
        "question": "What can be concluded from the change in fruit placement?",
        "correct": "Students were more likely to choose fruit when it was easier to see",
        "distractors": ["Fruit became less fresh", "Students had less time to eat", "Lunch prices dropped for everyone"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A construction crew covered stacks of lumber before a storm arrived. The next morning, framing work continued without delay.",
        "question": "Why did work continue without delay?",
        "correct": "The lumber was protected from the rain",
        "distractors": ["The storm changed direction", "The crew bought new tools", "The building plans were simplified"],
    },
    {
        "skill_tag": "main_idea_detail_inference",
        "passage": "A gym moved popular free weights away from the entrance so members would not crowd the doorway. People could enter and leave more smoothly afterward.",
        "question": "Why were the weights moved?",
        "correct": "To reduce congestion near the entrance",
        "distractors": ["To lower membership fees", "To shorten workout sessions", "To create more parking"],
    },
]


def _wk_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    word, correct_text, distractors = WK_BANK[index % len(WK_BANK)]
    return _text_question(
        "WK",
        "synonym",
        difficulty_level,
        f'The word "{word}" most nearly means:',
        [correct_text, *distractors],
        correct_text,
        f'"{word}" most nearly means "{correct_text}".',
        "Replace the word with the closest everyday meaning.",
        "This choice does not match the word's meaning in standard usage.",
    )


def _pc_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    item = PC_BANK[index % len(PC_BANK)]
    return _text_question(
        "PC",
        str(item["skill_tag"]),
        difficulty_level,
        f'Read the passage: {item["passage"]} {item["question"]}',
        [str(item["correct"]), *[str(choice) for choice in item["distractors"]]],
        str(item["correct"]),
        "Use the passage details to connect the action to its stated result.",
        "Match the question to the cause, result, or inference stated in the passage.",
        "This option is not supported by the passage.",
    )


def _gs_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("GS", difficulty_level, index)
    template = index % 4
    if template == 0:
        question = (
            "Which organ system is primarily responsible for moving oxygen through the body?"
        )
        options = ["Circulatory system", "Digestive system", "Skeletal system", "Nervous system"]
        return _text_question("GS", "biology_systems", difficulty_level, question, options, "Circulatory system",
                               "The circulatory system moves oxygen-rich blood throughout the body.",
                               "Look for the system that transports materials.", "The other systems perform support, digestion, or control functions.")
    if template == 1:
        question = "What happens to water when it reaches 100°C at sea level?"
        options = ["It boils", "It freezes", "It turns into metal", "It becomes heavier"]
        return _text_question("GS", "physics_states_of_matter", difficulty_level, question, options, "It boils",
                               "At sea level, water boils at 100°C.",
                               "Check the phase-change facts before picking a distractor.", "The other options do not match the boiling point of water.")
    if template == 2:
        question = "Which of these is a renewable resource?"
        options = ["Wind", "Coal", "Oil", "Natural gas"]
        return _text_question("GS", "earth_science_resources", difficulty_level, question, options, "Wind",
                               "Wind is naturally replenished and does not run out the way fossil fuels do.",
                               "Look for a resource that is naturally replaced.", "The other choices are finite fossil fuels.")
    question = "Which part of a plant absorbs water and minerals from the soil?"
    options = ["Roots", "Leaves", "Petals", "Fruit"]
    return _text_question("GS", "biology_plants", difficulty_level, question, options, "Roots",
                          "Roots anchor the plant and absorb water and minerals.",
                          "Focus on the plant structure that sits in the soil.", "The other choices do not absorb water from the ground.")


def _ei_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("EI", difficulty_level, index)
    template = index % 4
    if template == 0:
        voltage = rng.choice([6, 9, 12, 18, 24])
        resistance = rng.choice([2, 3, 4, 6, 8])
        current = voltage / resistance
        return _mcq(
            section="EI",
            skill_tag="ohms_law",
            difficulty_level=difficulty_level,
            question_text=f"If a circuit has {voltage} volts and {resistance} ohms, what is the current?",
            correct_text=f"{_format_number(current)} amps",
            distractors=[f"{_format_number(current + 1)} amps", f"{_format_number(max(1, current - 1))} amps", f"{_format_number(current * resistance)} amps"],
            base_explanation=f"Use Ohm's law: I = V / R = {voltage} / {resistance} = {_format_number(current)} amps.",
            quick_method="Divide voltage by resistance.",
            wrong_reason="This answer uses the wrong variable or the wrong operation.",
        )
    if template == 1:
        question = "In a series circuit, what happens to current through each component?"
        options = ["It is the same through every component", "It becomes zero after the first bulb", "It doubles at each bulb", "It changes direction every second"]
        return _text_question("EI", "series_circuit", difficulty_level, question, options, "It is the same through every component",
                               "Series circuits have one path, so the current is the same everywhere.",
                               "Remember that one path means one current value.", "The other choices do not describe a series circuit.")
    if template == 2:
        question = "Which component is used to store electrical charge briefly?"
        options = ["Capacitor", "Resistor", "Switch", "Fuse"]
        return _text_question("EI", "components", difficulty_level, question, options, "Capacitor",
                               "Capacitors store charge briefly and release it when needed.",
                               "Pick the component that stores charge, not one that limits or interrupts current.", "The other components serve different circuit roles.")
    question = "What is the primary purpose of a fuse in a circuit?"
    options = ["Protect the circuit from excessive current", "Increase voltage", "Store charge", "Measure resistance"]
    return _text_question("EI", "circuit_protection", difficulty_level, question, options, "Protect the circuit from excessive current",
                          "A fuse melts when current gets too high, opening the circuit.",
                          "Choose the protection device, not a measuring or storage device.", "The other choices do not protect against overcurrent.")


def _ai_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    template = index % 4
    rng = _rng("AI", difficulty_level, index)
    if difficulty_level <= 2:
        if template == 0:
            question = "What does the alternator do in a vehicle?"
            options = ["Charges the battery while the engine is running", "Cools the brake pads", "Inflates the tires", "Mixes the fuel and air"]
            return _text_question("AI", "electrical_system", difficulty_level, question, options, "Charges the battery while the engine is running",
                                   "The alternator supplies electrical power and recharges the battery.",
                                   "Think about the part that makes electricity while the engine runs.", "The other choices describe unrelated systems.")
        if template == 1:
            question = "Why is engine oil important?"
            options = ["It reduces friction and helps cool moving parts", "It makes the tires larger", "It raises the octane rating of fuel", "It replaces the coolant"]
            return _text_question("AI", "engine_oil", difficulty_level, question, options, "It reduces friction and helps cool moving parts",
                                   "Oil lubricates moving engine parts and helps carry away heat.",
                                   "Choose the option about lubrication and heat transfer.", "The other options are not the main job of oil.")
        if template == 2:
            question = "What does the brake system do?"
            options = ["Slows or stops the vehicle", "Increases the engine size", "Raises the windshield", "Cleans the fuel tank"]
            return _text_question("AI", "brakes", difficulty_level, question, options, "Slows or stops the vehicle",
                                   "Brakes convert motion into heat and slow the vehicle down.",
                                   "Select the function that directly affects vehicle speed.", "The other choices are unrelated to braking.")
        question = "What part stores electrical energy for starting the engine?"
        options = ["Battery", "Radiator", "Muffler", "Spark plug"]
        return _text_question("AI", "battery", difficulty_level, question, options, "Battery",
                              "The battery stores electrical energy and powers the starter.",
                              "Pick the energy-storage component, not the cooling or exhaust part.", "The other choices do not store electrical energy.")

    if difficulty_level == 3:
        if template == 0:
            symptom = rng.choice([
                "the headlights dim when the engine is idling and brighten when it revs",
                "the battery keeps going dead even after a new battery is installed",
                "the dash warning light for charging stays on while driving",
            ])
            question = f"A vehicle shows {symptom}. Which system should be checked first?"
            options = ["Charging system", "Tire pressure system", "Exhaust system", "Windshield system"]
            return _text_question("AI", "charging_system", difficulty_level, question, options, "Charging system",
                                   "Those symptoms point to a charging problem, often the alternator or wiring.",
                                   "Look for the system that keeps the battery powered while the engine runs.",
                                   "The other choices do not explain the electrical symptoms.")
        if template == 1:
            symptom = rng.choice([
                "the engine makes a single click but will not crank",
                "the starter turns slowly even though the battery tests good",
                "turning the key only gives a weak grinding noise",
            ])
            question = f"When starting a car, {symptom}. Which part is the best first check?"
            options = ["Starter system", "Fuel filter", "Radiator cap", "Brake shoes"]
            return _text_question("AI", "starter_system", difficulty_level, question, options, "Starter system",
                                   "Those symptoms point to the starter, solenoid, or related starting circuit.",
                                   "Think about the part that physically turns the engine over.",
                                   "The other choices are not part of the starting circuit.")
        if template == 2:
            symptom = rng.choice([
                "the temperature gauge climbs in traffic but drops on the highway",
                "the engine overheats even though the coolant level is full",
                "the heater blows cold air while the engine is getting too hot",
            ])
            question = f"A car has {symptom}. Which system should be inspected first?"
            options = ["Cooling system", "Charging system", "Steering system", "Ignition timing only"]
            return _text_question("AI", "cooling_system", difficulty_level, question, options, "Cooling system",
                                   "Those symptoms point to the radiator, thermostat, fan, or coolant flow.",
                                   "Choose the system that controls engine temperature.",
                                   "The other choices do not primarily control engine temperature.")
        symptom = rng.choice([
            "the engine hesitates when accelerating and fuel pressure reads low",
            "the engine stalls after a few minutes and a clogged fuel filter is suspected",
            "the engine starts but loses power under load",
        ])
        question = f"A vehicle {symptom}. Which system should be checked next?"
        options = ["Fuel system", "Brake system", "Airbag system", "Window regulator"]
        return _text_question("AI", "fuel_system", difficulty_level, question, options, "Fuel system",
                              "Fuel delivery problems can cause hesitation, stalling, or loss of power under load.",
                              "Focus on the system that supplies fuel to the engine.",
                              "The other choices do not match the driving symptom.")

    if difficulty_level == 4:
        if template == 0:
            symptom = rng.choice([
                "the brake pedal feels spongy after brake service",
                "the pedal sinks farther than usual when held down at a stop",
                "the brakes need pumping before the vehicle slows normally",
                "the pedal travels farther after a line bleed was done incorrectly",
                "one rear brake takes longer to engage and the pedal feels soft",
                "the stopping distance grows and the pedal feels springy on repeated stops",
            ])
            question = f"A car shows {symptom}. What is the most likely cause?"
            options = ["Air in the brake lines", "Too much coolant", "A loose lug nut", "A blocked muffler"]
            return _text_question("AI", "brake_hydraulics", difficulty_level, question, options, "Air in the brake lines",
                                   "Air compresses, which makes a hydraulic brake pedal feel soft or spongy.",
                                   "Think about what makes hydraulic pressure feel weak.",
                                   "The other choices do not explain a soft brake pedal.")
        if template == 1:
            symptom = rng.choice([
                "the battery tests weak and the engine needs jump starts more often",
                "headlights dim at idle but the battery is not the only issue",
                "a charging light comes on after the belt starts slipping",
                "the battery warning flickers when the blower and headlights are on",
                "the voltmeter drops below 13.0 V when accessories are running",
                "the battery keeps going dead overnight even after a full charge",
            ])
            question = f"A vehicle has {symptom}. Which part should be checked first?"
            options = ["Alternator and charging circuit", "Muffler", "Windshield washer pump", "Seat belt latch"]
            return _text_question("AI", "charging_system", difficulty_level, question, options, "Alternator and charging circuit",
                                   "Those symptoms are classic signs of a charging problem.",
                                   "Choose the system that recharges the battery while driving.",
                                   "The other choices do not affect battery charging.")
        if template == 2:
            symptom = rng.choice([
                "the temperature gauge rises in traffic even though coolant was recently topped off",
                "the radiator fan does not seem to come on when the engine is hot",
                "the upper radiator hose stays cool far too long after startup",
                "the temperature climbs after 10 minutes at idle and drops once driving starts",
                "the heater output turns cold while the engine is overheating",
                "the temperature falls quickly on the highway and rises again at stoplights",
            ])
            question = f"A vehicle has {symptom}. Which component is the best first suspect?"
            options = ["Thermostat or cooling fan control", "Fuel injector", "Door lock actuator", "Spark plug wire only"]
            return _text_question("AI", "cooling_system", difficulty_level, question, options, "Thermostat or cooling fan control",
                                   "These symptoms often point to a thermostat stuck closed or fan control failure.",
                                   "Focus on the parts that regulate coolant flow and airflow through the radiator.",
                                   "The other choices do not explain the overheating pattern.")
        symptom = rng.choice([
            "the engine cranks strongly but refuses to start and there is no fuel smell",
            "the vehicle loses power at highway speed after a fuel filter warning",
            "the engine surges as if it is starving for fuel",
            "fuel pressure drops from 40 psi to 25 psi under hard acceleration",
            "the engine starts, stalls after a few minutes, and restarts after cooling briefly",
            "the engine hesitates on hills even though spark and compression are normal",
        ])
        question = f"A vehicle has {symptom}. Which system is the best first check?"
        options = ["Fuel delivery system", "Battery terminals", "Exhaust tailpipe", "Cabin heater core"]
        return _text_question("AI", "fuel_system", difficulty_level, question, options, "Fuel delivery system",
                              "Those symptoms point to weak fuel delivery, such as the pump, filter, or injectors.",
                              "Look for the system that moves fuel to the engine under pressure.",
                              "The other choices do not directly cause fuel starvation.")

    if template == 0:
        symptom = rng.choice([
            "the engine misfires under load but seems smooth at idle",
            "the truck revs up but does not gain speed proportionally",
            "a service check finds unusual slip after acceleration",
            "the engine speed rises by 500 rpm during a shift without matching acceleration",
            "the fluid smells burnt and the vehicle shudders between second and third gear",
            "there is a delayed engagement after shifting from park to drive on a warm day",
        ])
        question = f"A vehicle has {symptom}. Which system is most likely at fault?"
        options = ["Transmission or drivetrain", "Wiper system", "Horn circuit", "Cabin air filter"]
        return _text_question("AI", "transmission_symptom", difficulty_level, question, options, "Transmission or drivetrain",
                               "Those symptoms usually point to slipping or power transfer problems in the drivetrain.",
                               "Think about where engine power reaches the wheels.",
                               "The other choices are unrelated to power transfer.")
    if template == 1:
        symptom = rng.choice([
            "the steering wheel pulls to one side after hitting a curb",
            "the tires wear unevenly across the tread",
            "the vehicle wanders and needs constant correction on a straight road",
            "the steering wheel sits off center even though the car drives straight",
            "the front tires squeal on normal turns after a pothole strike",
            "the vehicle drifts right more after braking from highway speed",
        ])
        question = f"A vehicle shows {symptom}. Which system should be checked next?"
        options = ["Steering and alignment", "Fuel system", "Cooling system", "Air intake filter"]
        return _text_question("AI", "steering_alignment", difficulty_level, question, options, "Steering and alignment",
                               "Those symptoms are classic signs of alignment or steering geometry issues.",
                               "Choose the system that affects wheel angle and road tracking.",
                               "The other choices do not explain tire wear or pulling.")
    if template == 2:
        symptom = rng.choice([
            "the engine overheats and the heater blows cold",
            "the coolant level drops but no external leak is visible",
            "the lower radiator hose stays cool much longer than expected",
            "the temperature rises, the oil light flickers, and compression still checks normal",
            "there is a milky residue on the oil cap and white smoke after startup",
            "coolant smell and bubbling continue in the overflow tank after a long drive",
        ])
        question = f"A vehicle has {symptom}. Which diagnosis is most likely?"
        options = ["Cooling system leak or thermostat problem", "Battery cable short", "Broken seat sensor", "Faulty door speaker"]
        return _text_question("AI", "engine_diagnostics", difficulty_level, question, options, "Cooling system leak or thermostat problem",
                               "Those clues point to a coolant flow or pressure problem.",
                               "Pick the diagnosis tied to coolant circulation and heat control.",
                               "The other choices are unrelated to overheating.")
    symptom = rng.choice([
        "the engine starts but stalls as soon as the throttle opens under load",
        "the dashboard warning lights flicker and the radio cuts out while driving",
        "the car hesitates, then recovers after a sharp downshift",
        "multiple electrical systems reset when the headlights and blower are switched on",
        "the battery voltage checks good, but the fault appears after hitting bumps",
        "fuses and relays test okay, yet the problem returns in wet weather",
    ])
    question = f"A vehicle has {symptom}. What is the best first system to inspect?"
    options = ["Electrical diagnostics and related circuits", "Windshield wipers", "Tire balancing only", "Interior trim"]
    return _text_question("AI", "electrical_diagnostics", difficulty_level, question, options, "Electrical diagnostics and related circuits",
                          "These symptoms require checking wiring, sensors, relays, and power delivery.",
                          "Look for the broad system that can explain several linked electrical symptoms.",
                          "The other options do not match the multi-symptom pattern.")


def _si_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    template = index % 4
    if template == 0:
        question = "Which tool is best for tightening a bolt with a hex head?"
        options = ["Wrench", "File", "Chisel", "Pliers"]
        return _text_question("SI", "hand_tools", difficulty_level, question, options, "Wrench",
                               "A wrench grips the flat sides of a hex head to apply torque.",
                               "Match the tool to the shape of the fastener.", "The other tools are not designed for this job.")
    if template == 1:
        question = "What is the main purpose of a caliper?"
        options = ["Measure inside, outside, or depth dimensions", "Cut sheet metal", "Weld two pieces together", "Paint a surface evenly"]
        return _text_question("SI", "measurement", difficulty_level, question, options, "Measure inside, outside, or depth dimensions",
                               "Calipers are precision measuring tools for multiple kinds of dimensions.",
                               "Look for the precision measuring tool.", "The other choices describe different shop tasks.")
    if template == 2:
        question = "Which fastening method can be removed and reused most easily?"
        options = ["Bolt and nut", "Glue", "Rivet", "Permanent weld"]
        return _text_question("SI", "fasteners", difficulty_level, question, options, "Bolt and nut",
                               "Bolts and nuts can be unfastened and reused more easily than permanent joints.",
                               "Choose the removable fastener.", "The other options are much more permanent.")
    question = "What does sandpaper primarily do?"
    options = ["Smooth a surface", "Add threads to metal", "Increase voltage", "Join two boards"]
    return _text_question("SI", "surface_finish", difficulty_level, question, options, "Smooth a surface",
                          "Sandpaper removes roughness and prepares a surface for finishing.",
                          "Think about a tool used to refine, not join or power, a surface.", "The other choices are not sanding tasks.")


def _mc_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("MC", difficulty_level, index)
    template = index % 4
    if template == 0:
        effort = rng.randint(10, 40)
        arm = rng.randint(2, 8)
        correct = effort * arm
        return _mcq(
            section="MC",
            skill_tag="lever",
            difficulty_level=difficulty_level,
            question_text=f"A {effort}-newton force is applied {arm} meters from a pivot on a lever. What is the torque?",
            correct_text=f"{correct} newton-meters",
            distractors=[f"{effort + arm} newton-meters", f"{effort - arm} newton-meters", f"{correct // 2} newton-meters"],
            base_explanation=f"Torque = force × distance, so {effort} × {arm} = {correct} newton-meters.",
            quick_method="Multiply force by the distance from the pivot.",
            wrong_reason="This answer uses addition or misses one of the values.",
        )
    if template == 1:
        gears = rng.choice([2, 3, 4, 5])
        direction = "counterclockwise"
        question = f"If a gear turns clockwise and it meshes with {gears - 1} other gears in a line, what direction does the last gear turn?"
        options = ["Clockwise", "Counterclockwise", "It stops", "It turns in both directions"]
        if (gears - 1) % 2 == 0:
            correct = "Clockwise"
        else:
            correct = "Counterclockwise"
        explanation = (
            "Each meshed gear reverses direction. Count the number of reversals from the first gear to the last."
        )
        return _text_question("MC", "gears", difficulty_level, question, options, correct, explanation, "Count each gear reversal.", "Meshed gears reverse direction one step at a time.")
    if template == 2:
        question = "Which simple machine is a ramp?"
        options = ["Inclined plane", "Wheel and axle", "Pulley", "Wedge"]
        return _text_question("MC", "simple_machines", difficulty_level, question, options, "Inclined plane",
                               "A ramp is an inclined plane, which reduces the force needed to raise an object.",
                               "Match the example to the machine type.", "The other choices are different simple machines.")
    question = "What happens to the pressure if the same force is applied over a smaller area?"
    options = ["Pressure increases", "Pressure decreases", "Pressure stays the same", "Pressure becomes zero"]
    return _text_question("MC", "pressure", difficulty_level, question, options, "Pressure increases",
                          "Pressure equals force divided by area, so smaller area means greater pressure.",
                          "Look at the force-over-area relationship.", "The other choices ignore the denominator effect.")


def _ao_question(difficulty_level: int, index: int) -> GeneratedQuestionDraft:
    rng = _rng("AO", difficulty_level, index)
    template = index % 4
    if template == 0:
        turns = rng.choice([1, 2, 3])
        final_direction = _rotate_direction("north", turns)
        question = f"A marker starts facing north and is rotated {turns * 90} degrees clockwise. Which direction does it face now?"
        options = ["North", "East", "South", "West"]
        return _text_question("AO", "rotation", difficulty_level, question, options, final_direction.title(),
                               "Rotate the direction one quarter-turn at a time.",
                               "Count the 90-degree turns carefully.", "The other directions are the results of different turn counts.")
    if template == 1:
        steps = rng.choice([1, 2, 3])
        question = f"A path moves one square east, then one square north, then repeats this pattern {steps} times. Which direction is the final net movement most like?"
        options = ["Northeast", "Northwest", "Southeast", "Southwest"]
        return _text_question("AO", "net_movement", difficulty_level, question, options, "Northeast",
                               "Repeated east-and-north moves create a net movement to the northeast.",
                               "Trace the combined movement instead of the last step only.", "The other choices point to the wrong quadrant.")
    if template == 2:
        question = "If a shape is mirrored left-to-right, which feature changes?"
        options = ["Its left and right sides swap", "Its color changes", "Its size doubles", "Its number of corners changes"]
        return _text_question("AO", "mirror_image", difficulty_level, question, options, "Its left and right sides swap",
                               "A mirror image flips left and right without changing size or number of corners.",
                               "Look for the property of a reflection.", "The other choices are not effects of mirroring.")
    question = "A cube is rotated so that the top face becomes the front face. What type of motion is this?"
    options = ["Rotation", "Scaling", "Translation", "Reflection"]
    return _text_question("AO", "3d_orientation", difficulty_level, question, options, "Rotation",
                          "Reorienting a solid without changing its size is a rotation.",
                          "Identify the transformation that changes orientation only.", "The other choices do not describe this movement.")


def _text_question(
    section: str,
    skill_tag: str,
    difficulty_level: int,
    question_text: str,
    options: list[str],
    correct_text: str,
    explanation: str,
    quick_method: str,
    wrong_reason: str,
) -> GeneratedQuestionDraft:
    rng = _rng(section, skill_tag, difficulty_level, question_text)
    choices, correct_answer = _shuffle_choices(correct_text, [option for option in options if option != correct_text], rng)
    wrong_map = {
        key: explanation if key == correct_answer else wrong_reason for key in choices
    }
    return _finalize_draft(
        section=section,
        skill_tag=skill_tag,
        difficulty_level=difficulty_level,
        question_text=question_text,
        choices=choices,
        correct_answer=correct_answer,
        base_explanation=explanation,
        wrong_explanations=wrong_map,
        quick_method=quick_method,
    )


def _rotate_direction(direction: str, turns: int) -> str:
    order = ["north", "east", "south", "west"]
    index = order.index(direction)
    return order[(index + turns) % 4]


def generate_questions_for_section(
    section: str,
    *,
    questions_per_section: int,
    difficulty_levels: list[int],
) -> list[GeneratedQuestionDraft]:
    generators = {
        "AR": _ar_question,
        "MK": _mk_question,
        "WK": _wk_question,
        "PC": _pc_question,
        "GS": _gs_question,
        "EI": _ei_question,
        "AI": _ai_question,
        "SI": _si_question,
        "MC": _mc_question,
        "AO": _ao_question,
    }
    generator = generators.get(section)
    if generator is None:
        return []

    items: list[GeneratedQuestionDraft] = []
    for index in range(questions_per_section):
        difficulty = difficulty_levels[index % len(difficulty_levels)] if difficulty_levels else 3
        items.append(generator(difficulty, index))
    return items


def generate_questions_for_sections(
    sections: list[str],
    *,
    questions_per_section: int,
    difficulty_levels: list[int],
) -> list[GeneratedQuestionDraft]:
    items: list[GeneratedQuestionDraft] = []
    for section in sections:
        items.extend(
            generate_questions_for_section(
                section,
                questions_per_section=questions_per_section,
                difficulty_levels=difficulty_levels,
            )
        )
    return items
