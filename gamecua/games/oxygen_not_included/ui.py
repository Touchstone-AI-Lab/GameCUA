"""Visual cues for the English 1280x720 ONI preparation UI."""

import base64

import numpy as np

CUES = [
    (
        "loaded",
        (20, 689, 54, 708),
        None,
        "JCUkGBYlKSkoJygoKCcoKCgmJSQjJCMjIyAeHxsZFAkkJSUoJiEiIyMfFxcWERMUExMQExQTExQVFRUWBQAGECUlJigoJCV0nIKNNx8kIxsbIiUfFyIlGxodHiAIAQkSJSUlJSQjJJCve7pPUISUdH2gdFZlqZeKLx0XEAUGDRQkJCQkJCMkj61PpHmPjqGPWY6MZo/DhYQsAAMMFRobGyQkJCQkIyWDrm2ibKCcmIVheaiIaah0ZSAACxoeHRwdJSUlJSQmJi86QDgpMz83NjU2NCMmNT43HA0ICREZHBwlJCQkJSUmJCEjJykmJCQlJB0hJCMiISMmKREABRYcHA==",
    ),
    (
        "mod_notice",
        (421, 251, 858, 274),
        (0.5, 0.597),
        "UlRUVFRUVFRUVFRUVFFQUFBQUFRUVFRUVFRUVFRUVFRSVFRUVFRUVFRUVFNXdIJ8f4OBVlRUVFRUVFRUVFRUVFJUVFRUVFRUVFRUU1ytsJelrZRUVFRUVFRUVFRUVFRUUlRUVFRUVFRUVFRTXrudna6qjVdUVFRUVFRUVFRUVFRSVFRUVFRUVFRUVFNbraSQn6OBWlNUVFRUVFRUVFRUVFJUVFRUVFRUVFRUU1iKqJSbko1YU1RUVFRUVFRUVFRUVFZWVlZWVlZWVlZWVldXV1dXWFZWVlZWVlZWVlZWVlY1NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2Ng==",
    ),
    (
        "safe_mode",
        (452, 259, 828, 279),
        (0.5, 0.592),
        "VFRUVFRUVFRUVFRUUlBRUFBRUFFUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRmdnB3dGp5bFNUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVJq1ma6Zo7uKUVRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUrKWWsp60qItRVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFSjp4ytj6qsg1FUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVIStmZeMjrOMUVRUVFRUVFRUVFRUVlZWVlZWVlZWVlZWWVxcW1taXFtWVlZWVlZWVlZWVlY5OTk5OTk5OTk5OTk4Nzg4ODg3ODk5OTk5OTk5OTk5OQ==",
    ),
    (
        "resume",
        (75, 169, 232, 193),
        (0.118, 0.262),
        "XFxbVldYVllWWVlZWFtYWFZcV1ZZVllZWllWWFxcXFxcW2W0mIy0g7mLhouRaI2XsmCYtIW2hoR2h7CVWVxcXFxacMW6uJChpoirrMeUyb2OYb+NpcGxvam8t3haXFxcXFpvw7Czj6GigKmpzNHLuo1jrH6rvaza1ra1d1pcXFxcWm7Wsre3gMWzo6m/773EsWapp7nVq9rnrc2RWVxcXFxacqurs3Zijbixs7GftbdwYLKxtZuur6m0o2NbXFxcXFptnpqqzZzXkcyvmmOdsspistGhkqKKd5rPpVhcXFxcXF1fX11iYGJbYF5fXV9dYlxeYV9fYF5eXmBhXFxcXA==",
    ),
    (
        "intro",
        (1192, 62, 1216, 89),
        (0.941, 0.104),
        "Hh4lOV+Rq59vRSgbGBkcHh8fHhwZGBsnQmqOnotiOiNBfsHr//////rnyaJ3Ti8dGBgeLkx1oMfm+P////3ixCY8X4i02PH////////13LePl7fc9v///////vDZtYlnHhwZGB0sRWqZyOv9//////////////rku41kQy0eGBgeHBkYHCpFa5vL7f7/////////////+N+wfE8uHhgYGyo/YYm32vP////////z27ubrczq////////9t+8kWRGQXu/6f3////45MaedE4wHxkaJT5ql8Dh9f/////306seHSY7Xoybg2BAKRwZGhweHx8fHBkbJjxfi6englk2JA==",
    ),
    (
        "base_resume",
        (1045, 219, 1255, 242),
        (0.895, 0.325),
        "XFxcXFxcXl1cXl5eXl1cXF9cXl1dXVxcX1xcXFxcXFxcXFxcXFefurGrw56Yn4KkwnLKpcGWhKfCYFtcXFxcXFxcXFxcWJu3qYOXjKq/sr+BeJqVsr2zvoBbXFxcXFxcXFxcXFxXorq0mrCTp8XcvKJ5mKrBxdu8oV1bXFxcXFxcXFxcXFekvrmMrLSjvuS4qnimusa+47mpXVtcXFxcXFxcXFxcWJasqmeGt7OuoLh9dbSzo62juHxbXFxcXFxcXFxcXFxZjJi5r8igxpN1pcJyzaWYl3enwl9bXFxcXFxcXFxcXFxeXl5gYFxfXV1dYFxfX15eXV1gXFxcXFxcXA==",
    ),
    (
        "loaded",
        (20, 689, 54, 708),
        None,
        "FhYVDxQkJyYkJCQlJSQkJSQiIiEgICAgHx0dHR0dGQwVFBQUEhAPDRAPBwcGAwUJCQcHCAcGBgUFBQQEBgcHBhMTExISDxBnkXSBJQkRFg8NFhkSChQXCQUIBQYKCwoEEhEQEBAOD4WobbI0NXWJZ3GWaEdZoY9/Hg0ODxAQDAQPDxAPDw4Og6k9mWeAgpaCSISBWYa+e3grDxISEhELAw8QDw8QDA12pVyXXJaRjXdRcaF+XaFoViMPEQ0LEAkDDQsLCwsLDBYnLyMSHSogHyEsJhEUJS8jFREPCAkPCAcMDA4QERESEQ8PEBIREBERERAQEhIPDxARDwYGCgoHDA==",
    ),
    (
        "loaded",
        (20, 689, 54, 708),
        None,
        "KiooGxcmKiooJygpKSkoKSgmJiYkJSQkJCEfICEiHxMsLCwsKSQkJCQgGBkZFxcYGBcXFxgXFxkZGRobGx0fIS0tKywuLS55n4aPOCEoKCAeJyojHCYpIB4gICEhISIjLS0tLS4sLZS1grxQUYWWeICheFtqq5qNOCorKyoqKysuLi4vLi0ulLNZqX2Rj6OSXZKQbJTFiodCKSwsKysrLC4uLy8uLi+Is3SlcaOdmodlgayNcKx5aTwqKywtLCwrMC8vLzAwLzhFST8wOUQ8OzxFPy0wPkc9MC0tLS0sLCwxLy8vMDAxMC4uLzEuLS8uLS0tLy8uLS0uLi4tLSwsLA==",
    ),
    (
        "mod_notice",
        (421, 251, 858, 274),
        (0.5, 0.597),
        "LzAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDBUVlZWVlZWVlZWVlZWWFlZWlpaVlZWVlZWVlZWVlZWVlJUVFRUVFRUVFRUU1mVq5igp59WU1RUVFRUVFRUVFRUUlRUVFRUVFRUVFRTXbSjkaKnhVNUVFRUVFRUVFRUVFRSVFRUVFRUVFRUVFNduJ2crKmMWVNUVFRUVFRUVFRUVFJUVFRUVFRUVFRUU1qhspWioIlaU1RUVFRUVFRUVFRUUlRUVFRUVFRUVFRUVm5/dnlzdFZUVFRUVFRUVFRUVFRSVFRUVFRUVFRUVFRUUVBRUFFRVFRUVFRUVFRUVFRUVA==",
    ),
]


def preparation_action(image):
    """Return the first recognized preparation cue and the input that dismisses it."""
    for name, box, point, encoded in CUES:
        actual = np.asarray(image.crop(box).convert("L").resize((32, 8)), dtype=float).ravel()
        expected = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8).astype(float)
        if np.mean(np.abs(actual - expected)) >= 4:
            continue
        if name == "base_resume":
            x, y = point
            return name, {"type": "drag", "x": x, "y": y, "to_x": x, "to_y": y, "duration": 0.5}
        action = (
            {"type": "click", "x": point[0], "y": point[1], "button": "left"} if point else None
        )
        return name, action
    return None
