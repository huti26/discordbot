# Pixiv

## Functionality

### User Commands

```
[.p | .pn] [tags]
```

Posts an image from pixiv, `.p` posts sfw tagged images and `.pn` nsfw tagged images.

Optionally you can add a list of tags like in the following example

```
.p slowpoke "ice cream"
```

This request would fetch an image that is both tagged as "slowpoke" and as "ice cream". If a tag consists of multiple words,
it has to be wrappen by "". Tags on pixiv are case insensitive.

```
.pixiv database [tags]
```

Returns how many images there are in the database with the given tags.

```
.pixiv report [image_id] [reason]
```

Report any images which you think the bot should not post. Artists can be blacklisted completely as a result.

Usage Example

```
.pixiv report 123456 The artist posts gore under sfw
```

### Admin Commands

```
.pixiv blacklist [tag | nsfw_tag | artist]
```

Removes all matching entries from the database and filesystem. Does not allow any images to be downloaded in the future,
that match the blacklisted item.

```
.pixiv whitelist [tag | nsfw_tag | artist]
```

Removes an item from the blacklist and allows future downloads.

If a `tag` is blacklisted, no image tagged as such will be downloaded.

If a `nsfw_tag` is blacklisted, no nsfw image tagged as such will be downloaded.

If an `artist` is blacklisted, none of their art will be downloaded.

```
.pixiv check_reports
```

Prints all reports.

```
.pixiv wipe_reports
```

Wipes all reports.

## Architechture

Starting the Bot initializes the database and then starts two processes.

The first process is the actual `Discordbot` itself. It reads and responds to requests by checking the database for
entries. Aditionally, whenever a certain tag is requested, it sends that tag to the second process.

The second process is called `Image Fetcher Service`. Whenever this process receives a tag from the Discordbot, it
attempts to download images for that tag. Images are downloaded to the filesystem and their path and other information
is added to the database.

## Database

The database structure is a classic 3 tables many-to-many relationship.

Table 1 is called `Images` and contains information about all images in the filesystem. Every image has a unique id and
there is only 1 entry in this table for it.

Table 2 is called `Tags`. Every Pixiv image can be tagged with an infinite amount of tags such as "pokemon" or "
halloween". Every tag has a unique id and there is only 1 entry in this table for it.

Table 3 is called `ImageTags`. This Table models the relationship between images and tags. It has two fields, which
refer to an image_id and to a tag_id. As an example if an image with the image_id 1 is tagged as "pokemon" and "
halloween", which have tag_ids 17 and 25 respecively, there would be the following tuples in `ImageTags`

(1,17) (1,25)

Roughly, after downloading 100.000 images, there are 100.000 tags and 1.000.000 ImageTags.

