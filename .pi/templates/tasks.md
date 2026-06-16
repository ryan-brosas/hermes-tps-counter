---
purpose: Task decomposition with dependency tracking
updated: [date]
---

# Tasks: [bead-id]

## Task Metadata

```yaml
id: "1.1"
depends_on: []
parallel: true
conflicts_with: []
files: []
estimated_minutes: 30
```

## 1. Setup

### 1.1 [Prerequisite task]

```yaml
depends_on: []
parallel: false
files: ["package.json"]
```

- [ ] [Task description]

## 2. Core Implementation

### 2.1 [Primary task]

```yaml
depends_on: ["1.1"]
parallel: true
files: ["src/feature.ts"]
```

- [ ] [Task description]

### 2.2 [Secondary task]

```yaml
depends_on: ["1.1"]
parallel: true
files: ["src/utils.ts"]
```

- [ ] [Task description]

### 2.3 [Integration task]

```yaml
depends_on: ["2.1", "2.2"]
parallel: false
files: ["src/feature.ts", "src/utils.ts"]
```

- [ ] [Task description]

## 3. Testing

### 3.1 [Test task]

```yaml
depends_on: ["2.3"]
parallel: true
files: ["tests/feature.test.ts"]
```

- [ ] [Task description]

## 4. Verification

### 4.1 All tests pass

```yaml
depends_on: ["3.1"]
parallel: false
```

- [ ] `[test command]`
