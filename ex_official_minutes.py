"""Nominal regulation minutes from a reviewed, identity-bound official timeline."""


def minutes_from_timeline(starters, substitutions):
    if len(starters) != 11 or len(set(starters)) != 11 or any(not p for p in starters):
        raise ValueError("Require eleven distinct starters")
    active = dict.fromkeys(starters, 0)
    appeared = set(starters)
    minutes = {}
    previous = 0
    for when, outgoing, incoming in substitutions:
        if (type(when) is not int or not previous <= when <= 90 or outgoing not in active
                or not incoming or incoming in appeared):
            raise ValueError("Invalid substitution sequence")
        minutes[outgoing] = when - active.pop(outgoing)
        active[incoming] = when
        appeared.add(incoming)
        previous = when
    minutes.update({player: 90 - start for player, start in active.items()})
    if sum(minutes.values()) != 990:
        raise ValueError("Nominal minutes fail the team total")
    return minutes
