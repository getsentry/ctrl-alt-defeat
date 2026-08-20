extends RefCounted

## What the rack is on the way to combining, and what goes with what (GDD 5.3).
##
## Two answers of different kinds, kept in one place because the screen asks
## them in the same breath.
##
## `pending` is about this rack and these items. It needs the rules -- what is
## touching what, how many of each a recipe wants, which of two recipes wins an
## item they both ask for -- and those stay on the server, so this only holds
## the answer it was given.
##
## The catalogue is a fact about the game and never changes, so it is fetched
## once and answered from here. That is what lets a line follow the pointer:
## a line is wanted on hover and while dragging, and a line every frame cannot
## be a request every frame.

const APITypes = preload("res://scripts/api_types.gd")

var catalogue: APITypes.CombiningCatalogue = null
var pending: Array[APITypes.Pending] = []


func knows_the_catalogue() -> bool:
	return catalogue != null


## The item types this one appears in a recipe with. Empty until the catalogue
## has arrived, so a screen that draws lines before then simply draws none.
func partners_of(item_type: String) -> Array[String]:
	if catalogue == null:
		return []
	return catalogue.partners_of(item_type)


## What to call an item type on screen. The type itself where the catalogue has
## not arrived or has never heard of it, which beats an empty label.
func name_of(item_type: String) -> String:
	if catalogue == null:
		return item_type
	return catalogue.name_of(item_type)


## Whether a line should be drawn between these two. It says they appear in a
## recipe together and nothing more: whether they will actually combine is
## `pending`.
func goes_with(one: String, other: String) -> bool:
	return partners_of(one).has(other)


## The combinations that will happen when the battle starts.
func about_to_combine() -> Array[APITypes.Pending]:
	var settled: Array[APITypes.Pending] = []
	for waiting in pending:
		if waiting.complete():
			settled.append(waiting)
	return settled


## The ids of the items in each of those, one list per combination. What the
## glow joins up.
func groups_about_to_combine() -> Array:
	var groups := []
	for waiting in about_to_combine():
		groups.append(waiting.item_ids())
	return groups


## The recipe to label this item with while it is being collected, or null.
##
## The one it is furthest along, because an item can be a step towards several
## things at once and the nearest to done is the one the player is most likely
## working on. A finished one is never offered: the item is going to combine,
## and naming something else it could have been would only confuse.
func progress_for(item_id: String) -> APITypes.Pending:
	var best: APITypes.Pending = null
	for waiting in pending:
		if waiting.complete() or not waiting.names(item_id):
			continue
		if best == null or waiting.have > best.have:
			best = waiting
	return best


## What to write beside an item just put down: "Long Poll 2/3". Empty when the
## item is not on the way to anything.
func progress_label(item_id: String) -> String:
	var waiting := progress_for(item_id)
	if waiting == null:
		return ""
	return "%s %d/%d" % [name_of(waiting.makes), waiting.have, waiting.need]


## Forget everything about a rack. The catalogue is kept: it is the same game.
func forget_the_rack() -> void:
	pending = []
