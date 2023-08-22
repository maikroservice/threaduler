# Contributing to Threaduler

Welcome! Threaduler is a community project that aims to work for a wide
range of Python users and Python codebases. If you're trying Threaduler, your experience and what you can contribute are important to the project's success.

## Code of Conduct

Everyone participating in the Threaduler community, and in particular in our
issue tracker, pull requests, and chat, is expected to treat
other people with respect and more generally to follow the guidelines
articulated in the [Python Community Code of Conduct](https://www.python.org/psf/codeofconduct/).

## Getting started with development

### Setup

#### (1) Fork the Threaduler repository

Within Github, navigate to <https://github.com/maikroservice/threaduler> and fork the repository.

#### (2) Clone the Threaduler repository and enter into it

```bash
git clone git@github.com:<your_username>/threaduler.git
cd threaduler
```

#### (3) Create then activate a virtual environment

```bash
# On Windows, the commands may be slightly different. For more details, see
# https://python-poetry.org/docs/
poetry shell
```

#### (4) Install the requirements

```bash
poetry install
```

> **Note**
> You'll need Python 3.8 or higher to install all requirements listed in
> pyproject.toml

## First time contributors

If you're looking for things to help with, browse our [issue tracker](https://github.com/maikroservice/threaduler/issues)!

In particular, look for:

- [good first issues](https://github.com/maikroservice/threaduler/labels/good-first-issue)
- [good second issues](https://github.com/maikroservice/threaduler/labels/good-second-issue)
- [documentation issues](https://github.com/maikroservice/threaduler/labels/documentation)

You do not need to ask for permission to work on any of these issues.
Just fix the issue yourself, try to add a unit test or two and
[open a pull request](#submitting-changes).

To get help fixing a specific issue, it's often best to comment on the issue
itself. You're much more likely to get help if you provide details about what
you've tried and where you've looked (maintainers tend to help those who help
themselves). [gitter](https://gitter.im/python/typing) can also be a good place
to ask for help.

Interactive debuggers like `pdb` and `ipdb` are really useful for getting
started with the Threaduler codebase. This is a
[useful tutorial](https://realpython.com/python-debugging-pdb/).

It's also extremely easy to get started contributing to our sister project
[typeshed](https://github.com/python/typeshed/issues) that provides type stubs
for libraries. This is a great way to become familiar with type syntax.

## Submitting changes

Even more excellent than a good bug report is a fix for a bug, or the
implementation of a much-needed new feature. We'd love to have
your contributions.

We use the usual GitHub pull-request flow, which may be familiar to
you if you've contributed to other projects on GitHub.  For the mechanics,
see [our git and GitHub workflow help page](https://github.com/maikroservice/threaduler/wiki/Using-Git-And-GitHub),
or [GitHub's own documentation](https://help.github.com/articles/using-pull-requests/).

Anyone interested in Threaduler may review your code. One of the Threaduler core developers will merge your pull request when they think it's ready.

If your change will be a significant amount of work
to write, we highly recommend starting by opening an issue laying out
what you want to do.  That lets a conversation happen early in case
other contributors disagree with what you'd like to do or have ideas
that will help you do it.

The best pull requests are focused, clearly describe what they're for
and why they're correct, and contain tests for whatever changes they
make to the code's behavior.  As a bonus these are easiest for someone
to review, which helps your pull request get merged quickly!  Standard
advice about good pull requests for open-source projects applies; we
have [our own writeup](https://github.com/maikroservice/threaduler/wiki/Good-Pull-Request)
of this advice.

Also, do not squash your commits after you have submitted a pull request, as this
erases context during review. We will squash commits when the pull request is merged.

You may also find other pages in the
[Threaduler developer guide](https://github.com/python/Threaduler/wiki/Developer-Guides)
helpful in developing your change.

## Core developer guidelines

Core developers should follow these rules when processing pull requests:

- Always wait for tests to pass before merging PRs.
- Use "[Squash and merge](https://github.com/blog/2141-squash-your-commits)"
  to merge PRs.
- Delete branches for merged PRs (by core devs pushing to the main repo).
- Edit the final commit message before merging to conform to the following
  style (we wish to have a clean `git log` output):
  - When merging a multi-commit PR make sure that the commit message doesn't
    contain the local history from the committer and the review history from
    the PR. Edit the message to only describe the end state of the PR.
  - Make sure there is a *single* newline at the end of the commit message.
    This way there is a single empty line between commits in `git log`
    output.
  - Split lines as needed so that the maximum line length of the commit
    message is under 80 characters, including the subject line.
  - Capitalize the subject and each paragraph.
  - Make sure that the subject of the commit message has no trailing dot.
  - Use the imperative mood in the subject line (e.g. "Fix typo in README").
  - If the PR fixes an issue, make sure something like "Fixes #xxx." occurs
    in the body of the message (not in the subject).
  - Use Markdown for formatting.