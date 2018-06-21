#!/usr/bin/env python

import sys
import time
import urllib
import re
import ConfigParser
import oauth2 as oauth

import simplejson as json

if __name__=="__main__":
	cfg = ConfigParser.ConfigParser()
	cfg.read('tweet2fbpost.ini')

	verbose = cfg.get('general', 'verbose', '1') == '1'

	try:
		twitteruser = cfg.get('twitter', 'user')
	except:
		print "Need option 'user' in section 'twitter' in tweet2fbpost.ini"
		sys.exit(1)

	try:
		facebook_page = cfg.get('facebook', 'pageid')
		facebook_token = cfg.get('facebook', 'pagetoken')
	except:
		print "Need options 'pageid' and 'pagetoken' in section 'facebook' in tweet2fbpost.ini"
		sys.exit(1)


	try:
		lasttweet = int(cfg.get('twitter', 'lasttweet'))
	except:
		# It's ok not to have a lasttweet if this is the first run
		lasttweet = 0
		pass

	# Stupid twitter now requires us to use OAuth to get to public information
	oauth_token = oauth.Token(cfg.get('twitter', 'token'), cfg.get('twitter', 'secret'))
	oauth_consumer = oauth.Consumer(cfg.get('twitter', 'consumer'), cfg.get('twitter', 'consumersecret'))

	params = {
		"oauth_reversion": "1.0",
		"oauth_nonce": oauth.generate_nonce(),
		"oauth_timestamp": int(time.time()),
		"oauth_token": oauth_token.key,
		"oauth_consumer_key": oauth_consumer.key,
		"screen_name" : twitteruser,
		"trim_user" : 1,
		"include_entities": 0,
		}
	if lasttweet:
		params['since_id'] = lasttweet

	req = oauth.Request(method='GET',
						url='https://api.twitter.com/1.1/statuses/user_timeline.json',
						parameters=params)
	req.sign_request(oauth.SignatureMethod_HMAC_SHA1(), oauth_consumer, oauth_token)
	u = urllib.urlopen(req.to_url())

	result = u.read()
	try:
		d = json.loads(result)
	except:
		if re.search("Twitter is currently down for maintenance.", result):
			sys.exit(0)

		print "Unable to parse json: %s" % result
		sys.exit(1)

	if len(d):
		first = True
		newmax = lasttweet
		for t in sorted(d, key=lambda k: k['id']):
			if not first:
				# Sleep if there is more than one post to send, just so we
				# don't get rate limited or something
				time.sleep(10)
			else:
				first = False

			# Don't repost tweets that start with @, since they are typically
			# responses, and thus don't belong on fb.
			if t['text'].startswith('@'):
				continue

			txt = t['text'].encode('utf8')
			u = urllib.urlopen('https://graph.facebook.com/%s/feed' % facebook_page,
							   urllib.urlencode({'message': txt, 'access_token': facebook_token}),
							   )
			if u.getcode() != 200:
				print "Failed to post to fb, code: %s" % u.getcode()
				print u.read()
			else:
				u.read()
			u.close()
			if verbose:
				print "Sent '%s'" % txt

			if t['id'] > newmax:
				newmax = t['id']

		cfg.set('twitter', 'lasttweet', newmax)
		with open('tweet2fbpost.ini', 'w') as f:
			cfg.write(f)

