# renovels
This is parser module for [Melon](https://github.com/otaku-melons/melon) management system that provides support of [renovels.org](https://renovels.org) source.

## Collections
Table of available keys for `melon collect` command.
| Key | Available | Description |
|---|---|---|
| **&#x2011;&#x2011;period** | ❌ | Number of hours until the current moment, which constitutes the data parsing period. |
| **&#x2011;&#x2011;filters** | ❌ | Filtering query string. |
| **&#x2011;&#x2011;pages** | ❌ | Number of requested catalog pages. |

## Custom settings
Parser settings can be changed by editing file `renovels.json` in configurations directory.
```JSON
"example_1": ""
```
Option 1 description.
___
```JSON
"example_2": false
```
Option 2 description.
