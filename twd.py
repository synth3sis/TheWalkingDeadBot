#!/usr/bin/env python3

import sys
import argparse
import json
import sqlite3
import re
import Levenshtein


# Input validation for character name. Symbols accepted: '.-
def validate_inputs(args):
	if args.character is None and args.season is None and args.episode is None:
		print("[]")
		sys.exit(1)

	if args.character:
		pattern = r'^[a-zA-Z \'\.\-]+$'
		if not bool(re.match(pattern, args.character)):
			print("[]")
			sys.exit(1)



# Return the value of the similarities between strings using the Levenshtein algorithm (the lower the better)
def levenshtein_distance(name_given, name_compared):
	return Levenshtein.distance(name_given, name_compared)



# Return the best result for character contained in res (using the levenshtein function above)
def best_result(character_name, res):
	distances = []
	for i in range(0, len(res)):
		distances.append(levenshtein_distance(character_name, res[i]['name']))

	return res[distances.index(min(distances))]



# Return the death episode of the give character
def death_joins(character_id, cur):
	cur.execute(
		f"""SELECT ep.EpisodeNumber, ep.Season, ep.EpisodeInSeason, ep.ReleaseDate, ep.EpisodeTitle
			FROM Character AS ch
			INNER JOIN Episodes as ep ON ch.Death = ep.EpisodeNumber
			WHERE ch.Id = ?
		""", (character_id,)
	)

	death_episode = cur.fetchone()
	if death_episode is None or len(death_episode) == 0:
		death_episode = None

	return death_episode



# Return 'res', an array json-dumpable that contains all the requested episode information
# (== Given the episode number, all the new characters and the deaths)
def build_episode_res(args, cur):
	pattern = r'^[sS][0-9]{1,2}x[0-9]{1,3}$'

	if bool(re.match(pattern, args.episode)):
		seasons = [0,6,13,16,16,16,16,16,16,16,16,16]
		parts = args.episode.split("x")
		season = int(parts[0][1:])
		episode = int(parts[1])
		
		result = 0
		for i in range(1, len(seasons)):
			if season != i:
				result = result + seasons[i]
			else:
				result = result + episode
				break
		
		where_clause = "ep.EpisodeNumber = " + str(result)
	else:
		where_clause = "ep.EpisodeTitle = \"" + args.episode + "\" COLLATE NOCASE"

	cur.execute(
		"""SELECT ch.Name, ep.Season, ep.EpisodeInSeason, ep.EpisodeTitle
			FROM Character AS ch
			LEFT JOIN Episodes AS ep ON ch.FirstAppearance = ep.EpisodeNumber
			WHERE """ + where_clause + """
			ORDER BY ch.Id
		"""
	)
	first_appearances = cur.fetchall()

	cur.execute(
		"""SELECT ch.Name, ep.Season, ep.EpisodeInSeason, ep.EpisodeTitle
			FROM Character AS ch
			INNER JOIN Episodes as ep ON ch.Death = ep.EpisodeNumber
			WHERE """ + where_clause + """
			ORDER BY ep.EpisodeInSeason
		"""
	)
	deaths_in_episode = cur.fetchall()

	count = 0
	res = {'episode': [], 'first_appearances':[], 'deaths':[]}
	for app in first_appearances:
		if count == 0:
			res['episode'] = {'title':app[3], 'season':app[1], 'episode':app[2]}
			count = count + 1
		res['first_appearances'].append(app[0])

	count = 0
	for app in deaths_in_episode:
		res['deaths'].append(app[0])

	return res


# Return 'output' with the requested episode output extracted by res
def episode_output(res, args):
	if args.json:
		output = json.dumps(res)
	elif args.html:
		if res['episode'] != []:
			output = f"<h3>First Appearances in \"{res['episode']['title']}\" S{res['episode']['season']}x{res['episode']['episode']}</h3>"
			for app in res['first_appearances']:
				output += f"<br><p>{app}</p>"
			output += f"<br><h3>Deaths in \"{res['episode']['title']}\" S{res['episode']['season']}x{res['episode']['episode']}</h3>"
			for app in res['deaths']:
				output += f"<br><p>{app}</p>"
		else:
			output = f"<h3>There's no episode named \"{args.episode}\"<h3>"
	else:
		if res['episode'] != []:
			output = f"First Appearances in \"{res['episode']['title']}\" S{res['episode']['season']}x{res['episode']['episode']}:\n"
			for app in res['first_appearances']:
				output += f"  - {app}\n"

			output += f"\nDeaths in in \"{res['episode']['title']}\" S{res['episode']['season']}x{res['episode']['episode']}:\n"
			for app in res['deaths']:
				output += f"  - {app}\n"
		else:
			output = f"There's no episode named \"{args.episode}\""

	return output




# Return 'res', an array json-dumpable that contains all the requested season information
# (== Given the season number, all the new characters and the deaths)
def build_season_res(args, cur):
	cur.execute(
		"""SELECT ep.EpisodeInSeason, ch.Name
			FROM Character AS ch
			LEFT JOIN Episodes as ep ON ch.FirstAppearance = ep.EpisodeNumber
			WHERE ep.Season = ?
			ORDER BY ep.EpisodeInSeason
		""", (args.season,)
	)
	first_appearances = cur.fetchall()

	cur.execute(
			"""SELECT ep.EpisodeInSeason, ch.Name
			FROM Character AS ch
			INNER JOIN Episodes as ep ON ch.Death = ep.EpisodeNumber
			WHERE ep.Season = ?
			ORDER BY ep.EpisodeInSeason
		""", (args.season,)
	)
	deaths_in_season = cur.fetchall()

	res = {'first_appearances':[], 'deaths':[]}
	chars = []
	episode = 0
	for app in first_appearances:
		if episode == 0:
			chars = []
			chars.append(app[1])
			episode = app[0]
		elif app[0] == episode:
			chars.append(app[1])
		elif app[0] > episode:
			episode_obj = {'n':episode, 'characters':chars}
			res['first_appearances'].append(episode_obj)
			chars = []
			chars.append(app[1])
			episode = app[0]

	chars = []
	episode = 0
	for app in deaths_in_season:
		if episode == 0:
			chars = []
			chars.append(app[1])
			episode = app[0]
		elif app[0] == episode:
			chars.append(app[1])
		elif app[0] > episode:
			episode_obj = {'n':episode, 'characters':chars}
			res['deaths'].append(episode_obj)
			chars = []
			chars.append(app[1])
			episode = app[0]

	return res




# Return 'output' with the requested season output extracted by res
def season_output(res, args):
	if args.json:
		output = json.dumps(res)
	elif args.html:
		output = f"<p>New Characters in Season {args.season}:</p>"
		for app in res['first_appearances']:
			chars = ""
			for ch in app['characters']:
				chars += f"{ch}, "
			output += f"<br><p>Ep.{app['n']}: {chars[:-2]}</p>   "

		output += f"<br><p>Deaths in Season {args.season}:</p>   "
		for death in res['deaths']:
			chars = ""
			for ch in death['characters']:
				chars += f"{ch}, "
			output += f"<br><p>Ep.{death['n']}: {chars[:-2]}</p>"
	else:
		output = f"New Characters in Season {args.season}:"
		for app in res['first_appearances']:
			chars = ""
			for ch in app['characters']:
				chars += f"{ch}, "
			output += f"\n  Ep.{app['n']}: {chars[:-2]}"

		output += f"\nDeaths in Season {args.season}:"
		for death in res['deaths']:
			chars = ""
			for ch in death['characters']:
				chars += f"{ch}, "
			output += f"\n  Ep.{death['n']}: {chars[:-2]}"

	return output




# Return 'res', an array json-dumpable that contains all the requested character information
def build_character_res(args, cur):
	twd_episode_num = 177
	res = []

	cur.execute(
		"""SELECT ch.Id, ch.Name, ch.Actor, ep.Season, ep.EpisodeNumber, ep.EpisodeInSeason, ep.ReleaseDate, ep.EpisodeTitle
			FROM Character AS ch
			LEFT JOIN Episodes as ep ON ch.FirstAppearance = ep.EpisodeNumber
			WHERE ch.Name LIKE ?
		""", (f"{args.character}%",)
	)
	results = cur.fetchall()

	if not results or results is None:
		cur.execute(
			"""SELECT ch.Id, ch.Name, ch.Actor, ep.Season, ep.EpisodeNumber, ep.EpisodeInSeason, ep.ReleaseDate, ep.EpisodeTitle
				FROM Character AS ch
				LEFT JOIN Episodes as ep ON ch.FirstAppearance = ep.EpisodeNumber
				WHERE ch.Name LIKE ?
			""", (f"%{args.character}%",)
		)
		results = cur.fetchall()
		if not results:
			print(results)
			sys.exit(0)


	for row in results:
		character_id = row[0]
		death_episode = death_joins(character_id, cur)

		tmp = []
		for el in row:
			tmp.append(el)
		if death_episode is not None:
			for el in death_episode:
				tmp.append(el)

		if tmp[4] is not None:
			lifespan = twd_episode_num - tmp[4] + 1
		else:
			lifespan = 0

		res.append({
			'name':			tmp[1],
			'actor':		tmp[2],
			'fs_numep':		tmp[4]	if tmp[4] is not None else 0,
			'fs_season':	tmp[3]	if tmp[3] is not None else 0,
			'fs_episode':	tmp[5]	if tmp[5] is not None else 0,
			'fs_release':	tmp[6]	if tmp[6] is not None else "",
			'fs_eptitle':	tmp[7]  if tmp[7] is not None else "",
			'd_numep':		tmp[8]	if death_episode is not None else 0,
			'd_season':		tmp[9]	if death_episode is not None else 0,
			'd_episode':	tmp[10]	if death_episode is not None else 0,
			'd_release':	tmp[11]	if death_episode is not None else "",
			'd_eptitle':	tmp[12]	if death_episode is not None else "",
			'lifespan':		tmp[8]-tmp[4]+1 if death_episode is not None else lifespan,
			'status':       "Alive" if death_episode is None else "Dead"
		})

	return res



# Return 'output' with the requested characteroutput extracted by res
def character_output(res, args):
	if args.json:
		output = json.dumps(res)
	elif args.html:
		output =  f"<p>{res['name']}:</p><br>"
		output += f"<p>First: S{res['fs_season']} ep.{res['fs_episode']} \"{res['fs_eptitle']}\"</p><br>"
		output += f"<p>Death: S{res['d_season']} ep.{res['d_episode']} \"{res['d_eptitle']}\"" if res['status'] == "Dead" else "Death: -</p><br>"
		output += f"<p>Status: {res['status']}</p>"
	else:
		output =  f"{res['name']}:\n"
		output += f"  First:  S{res['fs_season']} ep.{res['fs_episode']} \"{res['fs_eptitle']}\"\n"
		output += f"  Death:  S{res['d_season']} ep.{res['d_episode']} \"{res['d_eptitle']}\"\n" if res['status'] == "Dead" else "  Death:  -\n"
		output += f"  Status: {res['status']}"

	return output





# Main
def main():
	parser = argparse.ArgumentParser(description='Returns informations about The Walking Dead characters')
	parser.add_argument('--character', type=str, help='returns the character\'s first seen date and his death')
	parser.add_argument('--season', type=int, help='returns all the new characters and all the deaths of the season')
	parser.add_argument('--episode', type=str, help='returns all new characters and all the deaths in the episode')
	parser.add_argument('--json', action="store_true", help='if you want a JSON output format')
	parser.add_argument('--html', action="store_true", help='if you want a HTML output format (helpful with Telegram bot\'s output)')

	# Parse the arguments
	args = parser.parse_args()
	validate_inputs(args)

	conn = sqlite3.connect('twd.db')
	cur = conn.cursor()

	if args.character:							# user requested a character
		res = build_character_res(args, cur)	# build 'res' with character query output
		if len(res) > 0:
			res = best_result(args.character, build_character_res(args, cur))
		output = character_output(res, args)
	elif args.season:							# user requested a season
		res = build_season_res(args, cur)		# build 'res' with season query output
		output = season_output(res, args)
	elif args.episode:
		res = build_episode_res(args, cur)
		output = episode_output(res, args)

	print(output)
	cur.close()
	conn.close()


if __name__ == '__main__':
	main()
