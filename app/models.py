from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, Float
)
from sqlalchemy.orm import relationship
import enum

from .database import Base


class Difficulty(str, enum.Enum):
    B = "B"
    M = "M"
    H = "H"

DIFFICULTY_LABEL = {"B": "Базовий", "M": "Середній", "H": "Вищий"}

BLOOM_HINTS = {
    "B": "Базовий · Рівень 1–2 · Пригадати · Розуміти",
    "M": "Середній · Рівень 3–4 · Застосувати · Аналізувати",
    "H": "Вищий · Рівень 5–6 · Оцінити · Синтезувати",
}

BLOOM_DETAIL = {
    "B": {
        "title": "Базовий · Рівень 1–2 · Пригадати · Розуміти",
        "detail": "Студент відтворює або пояснює факти без трансформації. Відповіді конкретні й однозначні — перевіряють знання термінів, класифікацій, морфологічних та культуральних властивостей.",
        "verbs": "назвіть, перелічіть, визначте, охарактеризуйте, опишіть, вкажіть",
        "example": "«Перелічіть центральні органи імунної системи.»",
    },
    "M": {
        "title": "Середній · Рівень 3–4 · Застосувати · Аналізувати",
        "detail": "Студент використовує знання в нових ситуаціях або розкриває причинно-наслідкові зв'язки. Вимагає розуміння механізмів, а не лише їх відтворення.",
        "verbs": "поясніть механізм, порівняйте, чому, як відрізнити, що лежить в основі, доведіть",
        "example": "«Поясніть механізм активації системи комплементу класичним шляхом.»",
    },
    "H": {
        "title": "Вищий · Рівень 5–6 · Оцінити · Синтезувати",
        "detail": "Студент аргументує рішення в клінічному або нестандартному контексті. Вимагає інтеграції знань з різних тем і клінічного мислення.",
        "verbs": "обґрунтуйте, що станеться якщо, визначте тактику, запропонуйте, оцініть",
        "example": "«Обґрунтуйте вибір методу специфічної профілактики для пацієнта з імунодефіцитом.»",
    },
}


class QuestionType(str, enum.Enum):
    factual    = "factual"
    mechanism  = "mechanism"
    clinical   = "clinical"
    comparison = "comparison"

QUESTION_TYPE_LABEL = {
    "factual":    "Фактологічне",
    "mechanism":  "Механізм",
    "clinical":   "Клінічне",
    "comparison": "Порівняльне",
}

QUESTION_TYPE_HINT = {
    "factual":    "Відтворення фактів: терміни, переліки, класифікації, морфологія",
    "mechanism":  "Пояснення процесів і причинно-наслідкових зв'язків: патогенез, механізм дії",
    "clinical":   "Клінічна задача: симптоми, діагностика, вибір тактики лікування",
    "comparison": "Зіставлення об'єктів: відмінності, спільні риси, клінічне значення",
}

QUESTION_TYPE_DETAIL = {
    "factual": {
        "bloom": "Рівень Б",
        "detail": "Відтворення конкретних фактів без трансформації знань: терміни, класифікації, переліки ознак, морфологічні та культуральні властивості мікроорганізмів.",
        "example": "«Назвіть морфологічні особливості S. aureus та його тинкторіальні властивості.»",
    },
    "mechanism": {
        "bloom": "Рівень С–В",
        "detail": "Пояснення біологічних процесів і причинно-наслідкових зв'язків: патогенез, механізм дії препаратів, імунні реакції, механізми резистентності та вірулентності.",
        "example": "«Поясніть, як S. aureus долає фагоцитоз за допомогою факторів патогенності.»",
    },
    "clinical": {
        "bloom": "Рівень В",
        "detail": "Розв'язання клінічної задачі: аналіз симптомів, вибір методів мікробіологічної діагностики, тактика лікування, специфічна та неспецифічна профілактика. Найвищий рівень.",
        "example": "«Пацієнт з рецидивними гнійними інфекціями та зниженим IgG — яка тактика ведення?»",
    },
    "comparison": {
        "bloom": "Рівень С–В",
        "detail": "Зіставлення двох або більше об'єктів за спільними критеріями: відмінності у структурі, патогенності, лабораторній діагностиці чи клінічному значенні.",
        "example": "«Порівняйте первинну та вторинну імунну відповідь за швидкістю і рівнем антитіл.»",
    },
}


class QuestionStatus(str, enum.Enum):
    pending = "pending"
    active  = "active"
    retired = "retired"


class Role(str, enum.Enum):
    teacher = "teacher"
    admin   = "admin"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role          = Column(Enum(Role), default=Role.teacher, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    questions = relationship("Question", back_populates="author")
    votes     = relationship("Vote", back_populates="teacher")


class Faculty(Base):
    __tablename__ = "faculties"

    id         = Column(Integer, primary_key=True)
    name       = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    disciplines = relationship("Discipline", back_populates="faculty", order_by="Discipline.name")


class Discipline(Base):
    __tablename__ = "disciplines"

    id         = Column(Integer, primary_key=True)
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=False)
    name       = Column(String(200), nullable=False)
    code       = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    faculty = relationship("Faculty", back_populates="disciplines")
    modules = relationship("Module", back_populates="discipline", order_by="Module.number")


class Module(Base):
    __tablename__ = "modules"

    id            = Column(Integer, primary_key=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)
    name          = Column(String(200), nullable=False)
    number        = Column(Integer, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    discipline = relationship("Discipline", back_populates="modules")
    topics     = relationship("Topic", back_populates="module", order_by="Topic.number")
    tests      = relationship("Test", back_populates="module")


class Topic(Base):
    __tablename__ = "topics"

    id             = Column(Integer, primary_key=True)
    module_id      = Column(Integer, ForeignKey("modules.id"), nullable=False)
    name           = Column(String(300), nullable=False)
    number         = Column(Integer, nullable=False)
    is_high_stakes = Column(Boolean, server_default="0", default=False, nullable=False)
    hours_weight   = Column(Integer, server_default="1", default=1, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)

    module            = relationship("Module", back_populates="topics")
    questions         = relationship("Question", back_populates="topic")
    learning_outcomes = relationship("TopicLO", back_populates="topic",
                                     order_by="TopicLO.id",
                                     cascade="all, delete-orphan")


class TopicLO(Base):
    __tablename__ = "topic_learning_outcomes"

    id          = Column(Integer, primary_key=True)
    topic_id    = Column(Integer, ForeignKey("topics.id"), nullable=False)
    text        = Column(String(500), nullable=False)
    bloom_level = Column(Enum(Difficulty), nullable=True)

    topic = relationship("Topic", back_populates="learning_outcomes")


class Question(Base):
    __tablename__ = "questions"

    id                   = Column(Integer, primary_key=True)
    topic_id             = Column(Integer, ForeignKey("topics.id"), nullable=False)
    author_id            = Column(Integer, ForeignKey("users.id"), nullable=False)
    text                 = Column(Text, nullable=False)
    proposed_difficulty  = Column(Enum(Difficulty), nullable=False)
    final_difficulty     = Column(Enum(Difficulty), nullable=True)
    status               = Column(Enum(QuestionStatus), default=QuestionStatus.pending, nullable=False)
    question_type        = Column(Enum(QuestionType), nullable=True)
    learning_objective   = Column(String(500), nullable=True)
    learning_outcome_id  = Column(Integer, ForeignKey("topic_learning_outcomes.id"), nullable=True)
    model_answer         = Column(Text, nullable=True)
    current_round        = Column(Integer, server_default="1", default=1, nullable=False)
    created_at           = Column(DateTime, default=datetime.utcnow)
    # Cached empirical metrics — updated by _refresh_question_cache() after each result entry
    cached_p             = Column(Float, nullable=True)   # mean facility across all administrations
    cached_n_tested      = Column(Integer, nullable=True) # total students who have taken this question
    cached_d             = Column(Float, nullable=True)   # mean Ebel D (if upper/lower data available)
    cached_rec           = Column(String(10), nullable=True)  # last recommendation: retain/monitor/revise/retire

    topic           = relationship("Topic", back_populates="questions")
    author          = relationship("User", back_populates="questions")
    votes           = relationship("Vote", back_populates="question")
    test_questions  = relationship("TestQuestion", back_populates="question")
    results         = relationship("TestResult", back_populates="question")
    learning_outcome = relationship("TopicLO", foreign_keys=[learning_outcome_id])
    revisions       = relationship("QuestionRevision", back_populates="question",
                                   order_by="QuestionRevision.round")
    round_summaries = relationship("VoteRoundSummary", back_populates="question",
                                   order_by="VoteRoundSummary.round")


class Vote(Base):
    __tablename__ = "votes"

    id              = Column(Integer, primary_key=True)
    question_id     = Column(Integer, ForeignKey("questions.id"), nullable=False)
    teacher_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    approve         = Column(Boolean, nullable=False)
    difficulty_vote = Column(Enum(Difficulty), nullable=False)
    comment         = Column(Text, nullable=True)
    round           = Column(Integer, server_default="1", default=1, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    # Structured review criteria (1=poor, 2=acceptable, 3=good)
    crit_wording    = Column(Integer, nullable=True)  # clarity of stem + response scope
    crit_lo         = Column(Integer, nullable=True)  # ILO alignment
    crit_bloom      = Column(Integer, nullable=True)  # correct Bloom level
    crit_answer     = Column(Integer, nullable=True)  # model answer quality
    crit_accuracy   = Column(Integer, nullable=True)  # factual accuracy of stem + answer

    question = relationship("Question", back_populates="votes")
    teacher  = relationship("User", back_populates="votes")


class QuestionRevision(Base):
    """Snapshot of question text/answer/difficulty saved before each edit round."""
    __tablename__ = "question_revisions"

    id                  = Column(Integer, primary_key=True)
    question_id         = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    round               = Column(Integer, nullable=False)
    text                = Column(Text, nullable=False)
    model_answer        = Column(Text, nullable=True)
    proposed_difficulty = Column(Enum(Difficulty), nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="revisions")


class VoteRoundSummary(Base):
    """
    Aggregate snapshot of a review round at the moment it closes.
    Created when a question is activated, revised, or retired.
    Enables longitudinal analysis without recomputing from raw Vote rows.
    """
    __tablename__ = "vote_round_summaries"

    id                  = Column(Integer, primary_key=True)
    question_id         = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    round               = Column(Integer, nullable=False)
    outcome             = Column(String(20), nullable=False)  # activated | revised | retired
    n_votes             = Column(Integer, nullable=False)
    approval_pct        = Column(Float, nullable=True)   # % of approve votes
    # Per-criterion means (1–3 scale)
    mean_wording        = Column(Float, nullable=True)
    mean_lo             = Column(Float, nullable=True)
    mean_bloom          = Column(Float, nullable=True)
    mean_answer         = Column(Float, nullable=True)
    mean_accuracy       = Column(Float, nullable=True)
    # Per-criterion population SDs (inter-rater agreement indicator)
    sd_wording          = Column(Float, nullable=True)
    sd_lo               = Column(Float, nullable=True)
    sd_bloom            = Column(Float, nullable=True)
    sd_answer           = Column(Float, nullable=True)
    sd_accuracy         = Column(Float, nullable=True)
    # Difficulty consensus (% voting for the eventually-assigned tier)
    diff_consensus_pct  = Column(Float, nullable=True)
    closed_at           = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="round_summaries")


class Test(Base):
    __tablename__ = "tests"

    id            = Column(Integer, primary_key=True)
    name          = Column(String(200), nullable=False)
    module_id     = Column(Integer, ForeignKey("modules.id"), nullable=False)
    topic_id      = Column(Integer, ForeignKey("topics.id"), nullable=True)
    is_quiz       = Column(Boolean, default=False, nullable=False, server_default="0")
    created_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    batch_id      = Column(Integer, nullable=True)
    variant_label = Column(String(10), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    result_mean   = Column(Float, nullable=True)
    result_sd     = Column(Float, nullable=True)
    kr20          = Column(Float, nullable=True)  # KR-20 internal consistency for this administration
    exp_pass_rate = Column(Float, nullable=True)  # estimated pass rate (%) based on item facilities

    module         = relationship("Module", back_populates="tests")
    topic          = relationship("Topic", foreign_keys=[topic_id])
    creator        = relationship("User")
    test_questions = relationship("TestQuestion", back_populates="test", order_by="TestQuestion.order")
    results        = relationship("TestResult", back_populates="test")


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id          = Column(Integer, primary_key=True)
    test_id     = Column(Integer, ForeignKey("tests.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    order       = Column(Integer, nullable=False)

    test     = relationship("Test", back_populates="test_questions")
    question = relationship("Question", back_populates="test_questions")


class TestResult(Base):
    __tablename__ = "test_results"

    id             = Column(Integer, primary_key=True)
    test_id        = Column(Integer, ForeignKey("tests.id"), nullable=False)
    question_id    = Column(Integer, ForeignKey("questions.id"), nullable=False)
    correct_count  = Column(Integer, nullable=False)
    total_students = Column(Integer, nullable=False)
    # Optional discrimination data: upper/lower 27% of scorers
    upper_correct  = Column(Integer, nullable=True)
    lower_correct  = Column(Integer, nullable=True)
    recorded_at    = Column(DateTime, default=datetime.utcnow)

    test     = relationship("Test", back_populates="results")
    question = relationship("Question", back_populates="results")


class Setting(Base):
    __tablename__ = "settings"

    key   = Column(String(50), primary_key=True)
    value = Column(String(100), nullable=False)
