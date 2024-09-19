import requests
import time

# Your tokens and repository information
GITLAB_TOKEN = 'your_gitlab_token'
GITHUB_TOKEN = 'your_github_token'
GITLAB_PROJECT_ID = 'your_gitlab_project_id'
GITHUB_REPO = 'github_name/repo_name'

gitlab_headers = {'PRIVATE-TOKEN': GITLAB_TOKEN}
github_headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# How many entries to skip over at the start (if any)
SKIP_FIRST = 0 

# Function to fetch issues from GitLab with pagination and skipping the specified number of issues
def fetch_gitlab_issues(skip_first=0, start_page=1):
    issues = []
    page = start_page
    total_skipped = 0
    skip_done = False
    
    while True:
        gitlab_url = f'https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/issues?per_page=100&page={page}&order_by=created_at&sort=asc'
        response = requests.get(gitlab_url, headers=gitlab_headers)
        
        if response.status_code == 200:
            page_issues = response.json()
            
            if not page_issues:
                break  # No more issues, stop the loop

            if not skip_done:
                if total_skipped + len(page_issues) <= skip_first:
                    total_skipped += len(page_issues)
                else:
                    remaining_to_skip = skip_first - total_skipped
                    page_issues = page_issues[remaining_to_skip:]
                    issues.extend(page_issues)
                    skip_done = True
            else:
                issues.extend(page_issues)
            
            page += 1  # Move to the next page
        else:
            print(f"Failed to fetch issues from GitLab: {response.content}")
            break

    return issues

# Function to fetch comments for a specific issue from GitLab
def fetch_gitlab_comments(issue_iid):
    comments = []
    page = 1
    
    while True:
        gitlab_url = f'https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/issues/{issue_iid}/notes?per_page=100&page={page}'
        response = requests.get(gitlab_url, headers=gitlab_headers)
        
        if response.status_code == 200:
            page_comments = response.json()
            
            if not page_comments:
                break  # No more comments, stop the loop

            comments.extend(page_comments)
            page += 1  # Move to the next page
        else:
            print(f"Failed to fetch comments from GitLab for issue {issue_iid}: {response.content}")
            break

    return comments

# Function to close a GitHub issue
def close_github_issue(issue_number):
    github_url = f'https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}'
    issue_update = {'state': 'closed'}
    
    make_github_request_with_retry('PATCH', github_url, issue_update)

# Function to create a GitHub issue
def create_github_issue(title, body, labels, state):
    github_url = f'https://api.github.com/repos/{GITHUB_REPO}/issues'
    issue = {'title': title, 'body': body, 'labels': labels}

    response = make_github_request_with_retry('POST', github_url, issue)
    if response and response.status_code == 201:
        print(f'Successfully created issue: {title}')
        github_issue_number = response.json()['number']  # Return the GitHub issue number
        
        if state == 'closed':
            close_github_issue(github_issue_number)
            
        return github_issue_number
    else:
        print(f'Failed to create issue: {response.content}')
        return None

# Function to create a comment on a GitHub issue
def create_github_comment(issue_number, comment_body):
    github_url = f'https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/comments'
    comment = {'body': comment_body}

    make_github_request_with_retry('POST', github_url, comment)

# Helper function to make GitHub requests with retry handling on 403 errors
def make_github_request_with_retry(method, url, data=None):
    while True:
        try:
            response = requests.request(method, url, headers=github_headers, json=data)
            
            if response.status_code == 403:
                print(f"Rate limit or access issue detected (403). Retrying in 1 minute...")
                time.sleep(60)
                continue  # Retry after 1 minute
            elif response.status_code in [500, 502, 503, 504]:
                print(f"GitHub server error ({response.status_code}). Retrying in 5 seconds...")
                time.sleep(5)
                continue  # Retry after a short delay
            return response
        except requests.exceptions.Timeout:
            print(f"Request timed out. Retrying in 5 seconds...")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

# Main function to transfer issues and comments from GitLab to GitHub
def transfer_issues_and_comments():
    gitlab_issues = fetch_gitlab_issues(skip_first=SKIP_FIRST, start_page=1)
    
    for issue in gitlab_issues:
        title = issue['title']
        created_at = issue['created_at']
        body = issue['description']
        formatted_body = f"**Issue created at {created_at}**\n\n{body}"

        labels = issue.get('labels', [])
        state = issue.get('state')

        print(f"Issue: {title}, Labels: {labels}, State: {state}")

        github_issue_number = create_github_issue(title, formatted_body, labels, state)
        
        if github_issue_number:
            gitlab_comments = fetch_gitlab_comments(issue['iid'])
            
            for comment in gitlab_comments:
                comment_username = comment['author']['username']
                comment_created_at = comment['created_at']
                comment_body = comment['body']
                formatted_comment_body = f"**Comment by {comment_username} on {comment_created_at}**\n\n{comment_body}"

                create_github_comment(github_issue_number, formatted_comment_body)

if __name__ == '__main__':
    transfer_issues_and_comments()
